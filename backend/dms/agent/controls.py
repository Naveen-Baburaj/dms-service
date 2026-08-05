from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
import signal
import threading
import time
import uuid
from typing import Any, Callable, Iterator

import frappe

from dms.agent.types import ToolContext


RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""

CONCURRENCY_ACQUIRE_LUA = """
local now = tonumber(ARGV[1])
local expires_at = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local token = ARGV[4]
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
local current = redis.call('ZCARD', KEYS[1])
if current >= limit then
  return {0, current}
end
redis.call('ZADD', KEYS[1], expires_at, token)
redis.call('EXPIRE', KEYS[1], math.max(1, math.ceil(expires_at - now)))
return {1, current + 1}
"""

CONCURRENCY_RELEASE_LUA = """
return redis.call('ZREM', KEYS[1], ARGV[1])
"""

DEV_AUTH_HEADERS = (
    "x-user-role",
    "x-tenant-id",
)
SENSITIVE_KEY_TOKENS = (
    "authorization",
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "cookie",
)


class AgentControlError(RuntimeError):
    """Base exception for deterministic agent execution controls."""


class AgentRateLimitError(AgentControlError):
    pass


class AgentConcurrencyError(AgentControlError):
    pass


class AgentToolTimeoutError(AgentControlError, TimeoutError):
    pass


@dataclass(frozen=True)
class ControlDecision:
    enabled: bool
    key_fingerprint: str | None = None
    current: int | None = None
    limit: int | None = None
    ttl_seconds: int | None = None


@dataclass(frozen=True)
class ConcurrencyLease:
    enabled: bool
    key: str | None = None
    token: str | None = None
    current: int | None = None
    limit: int | None = None


def _conf_value(name: str, default: Any = None) -> Any:
    return os.getenv(name.upper()) or frappe.conf.get(name) or default


def _conf_bool(name: str, default: bool) -> bool:
    value = _conf_value(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _conf_int(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = _conf_value(name, default)
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def controls_enabled() -> bool:
    return _conf_bool("dms_agent_controls_enabled", True)


def controls_fail_closed() -> bool:
    return _conf_bool("dms_agent_controls_fail_closed", True)


def production_auth_required() -> bool:
    return _conf_bool("dms_production_auth_required", False)


def audit_enabled() -> bool:
    return _conf_bool("dms_agent_audit_enabled", True)


def _header(name: str) -> str:
    try:
        return str(frappe.get_request_header(name) or "").strip()
    except Exception:
        return ""


def _site_name() -> str:
    try:
        value = str(frappe.local.site or "").strip()
    except Exception:
        value = ""
    return value or "unknown-site"


def _cache():
    candidate = getattr(frappe, "cache", None)
    if callable(candidate):
        try:
            candidate = candidate()
        except TypeError:
            pass
    if candidate is None:
        raise AgentControlError("Frappe Redis cache is unavailable")
    return candidate


def _redis_eval(script: str, keys: list[str], arguments: list[Any]) -> Any:
    cache = _cache()
    evaluator = getattr(cache, "eval", None)
    if not callable(evaluator):
        raise AgentControlError("Frappe Redis cache does not expose eval")
    return evaluator(script, len(keys), *(keys + [str(item) for item in arguments]))


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "<redacted>"
                if any(token in str(key).lower() for token in SENSITIVE_KEY_TOKENS)
                else _normalise(child)
            )
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return [_normalise(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _normalise(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _request_id() -> str:
    for name in ("x-client-request-id", "x-request-id"):
        value = _header(name)
        if value:
            return value[:128]
    return str(uuid.uuid4())


def _client_ip() -> str:
    forwarded = _header("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:128]
    try:
        return str(frappe.local.request_ip or "").strip()[:128]
    except Exception:
        return ""


def _session_user() -> str:
    try:
        return str(frappe.session.user or "Guest").strip() or "Guest"
    except Exception:
        return "Guest"


def auth_contract_decision(
    *,
    user: str,
    has_development_headers: bool,
    production_required: bool,
) -> tuple[bool, str]:
    if not production_required:
        return True, "development_auth_allowed"
    if not user or user == "Guest":
        return False, "authenticated_frappe_session_required"
    if has_development_headers:
        return False, "development_headers_forbidden"
    return True, "authenticated_frappe_session"


def enforce_request_auth() -> dict[str, Any]:
    has_dev_headers = any(_header(name) for name in DEV_AUTH_HEADERS)
    allowed, mode = auth_contract_decision(
        user=_session_user(),
        has_development_headers=has_dev_headers,
        production_required=production_auth_required(),
    )
    if not allowed:
        raise PermissionError(mode)
    return {
        "allowed": True,
        "mode": mode,
        "production_auth_required": production_auth_required(),
        "development_headers_present": has_dev_headers,
    }


def _request_identity() -> str:
    parts = [
        _site_name(),
        _session_user(),
        _header("x-client-user-id"),
        _header("x-tenant-id"),
        _client_ip(),
    ]
    return _fingerprint("|".join(parts))


def _tool_identity(context: ToolContext) -> str:
    parts = [
        _site_name(),
        context.user,
        context.company_id or "",
        context.company_name or "",
        context.tenant_id or "",
    ]
    return _fingerprint("|".join(parts))


def _control_key(kind: str, identity: str, suffix: str = "") -> str:
    tail = f":{suffix}" if suffix else ""
    return f"dms-agent:{_site_name()}:{kind}:{identity}{tail}"


def _rate_limit(
    *,
    kind: str,
    identity: str,
    limit: int,
    window_seconds: int,
    suffix: str = "",
) -> ControlDecision:
    if not controls_enabled():
        return ControlDecision(enabled=False)
    key = _control_key(kind, identity, suffix)
    try:
        result = _redis_eval(
            RATE_LIMIT_LUA,
            [key],
            [window_seconds],
        )
        current = int(result[0])
        ttl = max(0, int(result[1]))
    except Exception:
        if controls_fail_closed():
            raise
        return ControlDecision(enabled=False)
    if current > limit:
        raise AgentRateLimitError(
            f"{kind} rate limit exceeded; retry after approximately {ttl} seconds"
        )
    return ControlDecision(
        enabled=True,
        key_fingerprint=_fingerprint(key),
        current=current,
        limit=limit,
        ttl_seconds=ttl,
    )


def enforce_request_rate_limit() -> ControlDecision:
    return _rate_limit(
        kind="request-rate",
        identity=_request_identity(),
        limit=_conf_int("dms_agent_rate_limit_requests", 60, 1, 10000),
        window_seconds=_conf_int(
            "dms_agent_rate_limit_window_seconds", 60, 1, 3600
        ),
    )


def enforce_tool_rate_limit(
    context: ToolContext,
    tool_name: str,
) -> ControlDecision:
    return _rate_limit(
        kind="tool-rate",
        identity=_tool_identity(context),
        suffix=_fingerprint(tool_name),
        limit=_conf_int("dms_agent_rate_limit_tools", 240, 1, 50000),
        window_seconds=_conf_int(
            "dms_agent_rate_limit_window_seconds", 60, 1, 3600
        ),
    )


def acquire_request_concurrency() -> ConcurrencyLease:
    if not controls_enabled():
        return ConcurrencyLease(enabled=False)
    identity = _request_identity()
    key = _control_key("request-concurrency", identity)
    token = str(uuid.uuid4())
    limit = _conf_int("dms_agent_max_concurrent_requests", 2, 1, 100)
    lease_seconds = _conf_int(
        "dms_agent_concurrency_lease_seconds", 180, 5, 1800
    )
    now = time.time()
    try:
        result = _redis_eval(
            CONCURRENCY_ACQUIRE_LUA,
            [key],
            [now, now + lease_seconds, limit, token],
        )
        acquired = int(result[0]) == 1
        current = int(result[1])
    except Exception:
        if controls_fail_closed():
            raise
        return ConcurrencyLease(enabled=False)
    if not acquired:
        raise AgentConcurrencyError(
            f"Concurrent DMS AI request limit reached ({current}/{limit})"
        )
    return ConcurrencyLease(
        enabled=True,
        key=key,
        token=token,
        current=current,
        limit=limit,
    )


def release_request_concurrency(lease: ConcurrencyLease) -> None:
    if not lease.enabled or not lease.key or not lease.token:
        return
    try:
        _redis_eval(
            CONCURRENCY_RELEASE_LUA,
            [lease.key],
            [lease.token],
        )
    except Exception:
        if controls_fail_closed():
            raise


def _logger():
    try:
        return frappe.logger("dms_agent_audit", allow_site=True)
    except TypeError:
        return frappe.logger("dms_agent_audit")


def _audit(event: dict[str, Any]) -> tuple[str | None, bool]:
    if not audit_enabled():
        return None, False
    audit_id = str(event.get("audit_id") or uuid.uuid4())
    payload = {
        "schema_version": 1,
        "audit_id": audit_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    try:
        _logger().info(_canonical_json(payload))
        return audit_id, True
    except Exception:
        return audit_id, False


def audit_tool_execution(
    *,
    context: ToolContext,
    tool_name: str,
    arguments: dict[str, Any],
    output: dict[str, Any],
    trace: dict[str, Any],
) -> tuple[str | None, bool]:
    error = str(trace.get("error") or "")
    return _audit(
        {
            "event": "tool_execution",
            "request_id": context.request_id,
            "user_fingerprint": _fingerprint(context.user),
            "scope_fingerprint": _hash(
                {
                    "role": context.role,
                    "tenant_id": context.tenant_id,
                    "company_id": context.company_id,
                    "company_name": context.company_name,
                    "is_admin": context.is_admin,
                }
            ),
            "tool": tool_name,
            "arguments_hash": _hash(arguments),
            "output_hash": _hash(output),
            "ok": bool(trace.get("ok")),
            "duration_ms": trace.get("duration_ms"),
            "output_chars": trace.get("output_chars"),
            "truncated": bool(trace.get("truncated")),
            "timed_out": bool(trace.get("timed_out")),
            "error_type": error.split(":", 1)[0] if error else None,
            "error_fingerprint": _fingerprint(error) if error else None,
        }
    )


def audit_request_execution(
    *,
    request_id: str,
    endpoint: str,
    input_value: Any,
    output_value: Any,
    ok: bool,
    duration_ms: float,
    error: BaseException | None,
    auth: dict[str, Any] | None,
    rate: ControlDecision | None,
    lease: ConcurrencyLease | None,
) -> tuple[str | None, bool]:
    error_text = (
        f"{type(error).__name__}: {str(error)}"
        if error is not None
        else ""
    )
    return _audit(
        {
            "event": "agent_request",
            "request_id": request_id,
            "endpoint": endpoint,
            "user_fingerprint": _fingerprint(_session_user()),
            "identity_fingerprint": _request_identity(),
            "input_hash": _hash(input_value),
            "output_hash": _hash(output_value),
            "ok": ok,
            "duration_ms": duration_ms,
            "auth_mode": (auth or {}).get("mode"),
            "rate_current": rate.current if rate else None,
            "rate_limit": rate.limit if rate else None,
            "concurrency_current": lease.current if lease else None,
            "concurrency_limit": lease.limit if lease else None,
            "error_type": type(error).__name__ if error else None,
            "error_fingerprint": _fingerprint(error_text) if error_text else None,
        }
    )


@contextmanager
def tool_timeout(seconds: int | float) -> Iterator[dict[str, Any]]:
    timeout_seconds = max(0.01, float(seconds))
    state = {
        "seconds": timeout_seconds,
        "mode": "elapsed_deadline",
    }
    hard_supported = (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
    )
    started = time.perf_counter()
    if not hard_supported:
        yield state
        elapsed = time.perf_counter() - started
        if elapsed > timeout_seconds:
            raise AgentToolTimeoutError(
                f"Tool exceeded {timeout_seconds:g} seconds"
            )
        return

    state["mode"] = "signal_itimer"
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _raise_timeout(_signum, _frame):
        raise AgentToolTimeoutError(
            f"Tool exceeded {timeout_seconds:g} seconds"
        )

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield state
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(
                signal.ITIMER_REAL,
                previous_timer[0],
                previous_timer[1],
            )


@contextmanager
def request_guard(
    *,
    endpoint: str,
    input_value: Any,
) -> Iterator[dict[str, Any]]:
    request_id = _request_id()
    previous_request_id = None
    try:
        previous_request_id = getattr(
            frappe.local,
            "dms_agent_request_id",
            None,
        )
        frappe.local.dms_agent_request_id = request_id
    except Exception:
        previous_request_id = None

    started = time.perf_counter()
    auth = None
    rate = None
    lease = None
    state: dict[str, Any] = {
        "request_id": request_id,
        "output_value": None,
    }
    error: BaseException | None = None
    ok = False
    try:
        auth = enforce_request_auth()
        rate = enforce_request_rate_limit()
        lease = acquire_request_concurrency()
        yield state
        ok = True
    except BaseException as exc:
        error = exc
        raise
    finally:
        try:
            if lease is not None:
                release_request_concurrency(lease)
        finally:
            audit_request_execution(
                request_id=request_id,
                endpoint=endpoint,
                input_value=input_value,
                output_value=state.get("output_value"),
                ok=ok,
                duration_ms=round(
                    (time.perf_counter() - started) * 1000,
                    2,
                ),
                error=error,
                auth=auth,
                rate=rate,
                lease=lease,
            )
            try:
                frappe.local.dms_agent_request_id = previous_request_id
            except Exception:
                pass


def guarded_agent_endpoint(function: Callable) -> Callable:
    @wraps(function)
    def wrapper(*args, **kwargs):
        input_value = {
            "args": args,
            "kwargs": kwargs,
        }
        endpoint = f"{function.__module__}.{function.__name__}"
        with request_guard(
            endpoint=endpoint,
            input_value=input_value,
        ) as guard_state:
            result = function(*args, **kwargs)
            guard_state["output_value"] = result
            return result

    return wrapper


def _delete_probe_keys(keys: list[str]) -> None:
    try:
        cache = _cache()
        delete = getattr(cache, "delete_value", None)
        if callable(delete):
            for key in keys:
                delete(key)
            return
        raw_delete = getattr(cache, "delete", None)
        if callable(raw_delete):
            raw_delete(*keys)
    except Exception:
        pass


def runtime_probe() -> dict[str, Any]:
    probe_id = str(uuid.uuid4())
    rate_key = _control_key("probe-rate", probe_id)
    concurrency_key = _control_key("probe-concurrency", probe_id)
    keys = [rate_key, concurrency_key]
    try:
        rate_first = _redis_eval(RATE_LIMIT_LUA, [rate_key], [30])
        rate_second = _redis_eval(RATE_LIMIT_LUA, [rate_key], [30])

        now = time.time()
        first_token = str(uuid.uuid4())
        second_token = str(uuid.uuid4())
        first = _redis_eval(
            CONCURRENCY_ACQUIRE_LUA,
            [concurrency_key],
            [now, now + 30, 1, first_token],
        )
        second = _redis_eval(
            CONCURRENCY_ACQUIRE_LUA,
            [concurrency_key],
            [now, now + 30, 1, second_token],
        )
        released = _redis_eval(
            CONCURRENCY_RELEASE_LUA,
            [concurrency_key],
            [first_token],
        )

        timeout_caught = False
        timeout_mode = None
        try:
            with tool_timeout(0.05) as timeout_state:
                timeout_mode = timeout_state["mode"]
                time.sleep(0.10)
        except AgentToolTimeoutError:
            timeout_caught = True

        audit_id, audit_logged = _audit(
            {
                "event": "controls_probe",
                "request_id": probe_id,
                "ok": True,
            }
        )

        auth_matrix = {
            "development_guest": auth_contract_decision(
                user="Guest",
                has_development_headers=True,
                production_required=False,
            ),
            "production_guest": auth_contract_decision(
                user="Guest",
                has_development_headers=False,
                production_required=True,
            ),
            "production_dev_headers": auth_contract_decision(
                user="Administrator",
                has_development_headers=True,
                production_required=True,
            ),
            "production_session": auth_contract_decision(
                user="Administrator",
                has_development_headers=False,
                production_required=True,
            ),
        }

        passed = all(
            [
                int(rate_first[0]) == 1,
                int(rate_second[0]) == 2,
                int(first[0]) == 1,
                int(second[0]) == 0,
                int(released) == 1,
                timeout_caught,
                bool(audit_id),
                audit_logged or not audit_enabled(),
                auth_matrix["development_guest"][0] is True,
                auth_matrix["production_guest"][0] is False,
                auth_matrix["production_dev_headers"][0] is False,
                auth_matrix["production_session"][0] is True,
            ]
        )
        if not passed:
            raise AssertionError("One or more execution-control probes failed")

        return {
            "status": "pass",
            "controls_enabled": controls_enabled(),
            "fail_closed": controls_fail_closed(),
            "production_auth_required": production_auth_required(),
            "audit_enabled": audit_enabled(),
            "redis_rate_limit": {
                "first": int(rate_first[0]),
                "second": int(rate_second[0]),
            },
            "redis_concurrency": {
                "first_acquired": int(first[0]) == 1,
                "second_denied": int(second[0]) == 0,
                "released": int(released) == 1,
            },
            "timeout": {
                "caught": timeout_caught,
                "mode": timeout_mode,
            },
            "audit": {
                "logged": audit_logged,
                "audit_id_present": bool(audit_id),
            },
            "auth_contract": {
                key: {"allowed": value[0], "mode": value[1]}
                for key, value in auth_matrix.items()
            },
        }
    finally:
        _delete_probe_keys(keys)
