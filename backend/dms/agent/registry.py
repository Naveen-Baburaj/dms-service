from __future__ import annotations

import importlib
import json
import pkgutil
import time
from typing import Any, Callable

from dms.agent.types import AgentTool, ToolContext
from dms.agent.controls import (
    AgentToolTimeoutError,
    audit_tool_execution,
    enforce_tool_rate_limit,
    tool_timeout,
)


_TOOLS: dict[str, AgentTool] = {}
_DISCOVERED = False


def register_tool(
    *,
    name: str,
    description: str,
    parameters: dict[str, Any],
    allowed_roles: set[str] | frozenset[str] | None = None,
    read_only: bool = True,
    timeout_seconds: int = 20,
    max_output_chars: int = 80_000,
) -> Callable:
    def decorator(handler: Callable) -> Callable:
        if name in _TOOLS:
            raise RuntimeError(f"Duplicate agent tool: {name}")
        _TOOLS[name] = AgentTool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            allowed_roles=frozenset(allowed_roles or {"*"}),
            read_only=read_only,
            timeout_seconds=max(1, int(timeout_seconds)),
            max_output_chars=max(1_000, int(max_output_chars)),
        )
        return handler
    return decorator


def discover_tools() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    package = importlib.import_module("dms.agent.tools")
    prefix = package.__name__ + "."
    for module_info in pkgutil.iter_modules(package.__path__, prefix=prefix):
        importlib.import_module(module_info.name)
    _DISCOVERED = True


def _role_allowed(tool: AgentTool, context: ToolContext) -> bool:
    if "*" in tool.allowed_roles:
        return True
    if context.role in tool.allowed_roles:
        return True
    return context.is_admin and "group_admin" in tool.allowed_roles


def available_tools(context: ToolContext) -> list[AgentTool]:
    discover_tools()
    return [
        tool for tool in _TOOLS.values()
        if tool.read_only and _role_allowed(tool, context)
    ]


def get_tool(name: str, context: ToolContext) -> AgentTool:
    discover_tools()
    tool = _TOOLS.get(name)
    if not tool:
        raise ValueError(f"Unknown backend capability: {name}")
    if not tool.read_only:
        raise PermissionError(
            f"Write-capable tool is disabled in this phase: {name}"
        )
    if not _role_allowed(tool, context):
        raise PermissionError(
            f"Current user cannot execute backend capability: {name}"
        )
    return tool


def openai_tool_definitions(
    context: ToolContext,
    *,
    names: list[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = available_tools(context)
    if names is not None:
        wanted = set(names)
        allowed = [tool for tool in allowed if tool.name in wanted]
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "strict": True,
        }
        for tool in allowed
    ]


def _validate(schema: dict[str, Any], value: Any, path: str) -> None:
    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                _validate(option, value, path)
                return
            except Exception as exc:
                errors.append(str(exc))
        raise ValueError(
            f"{path} does not match any allowed schema: {errors}"
        )

    expected = schema.get("type")
    if expected == "null":
        if value is not None:
            raise ValueError(f"{path} must be null")
        return
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ValueError(f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ValueError(
                    f"{path} contains unsupported properties: {extras}"
                )
        for key, child in value.items():
            if key in properties:
                _validate(properties[key], child, f"{path}.{key}")
        return
    if expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array")
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(value) < min_items:
            raise ValueError(
                f"{path} requires at least {min_items} item(s)"
            )
        if max_items is not None and len(value) > max_items:
            raise ValueError(
                f"{path} allows at most {max_items} item(s)"
            )
        item_schema = schema.get("items", {})
        for index, child in enumerate(value):
            _validate(item_schema, child, f"{path}[{index}]")
        return
    if expected == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"{path} must be one of {schema['enum']}")
        return
    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{path} must be an integer")
        if schema.get("minimum") is not None and value < schema["minimum"]:
            raise ValueError(f"{path} must be >= {schema['minimum']}")
        if schema.get("maximum") is not None and value > schema["maximum"]:
            raise ValueError(f"{path} must be <= {schema['maximum']}")
        return
    if expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path} must be a number")
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{path} must be a boolean")
        return
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of {schema['enum']}")


def execute_tool(
    *,
    name: str,
    arguments: dict[str, Any],
    context: ToolContext,
) -> tuple[dict[str, Any], dict[str, Any]]:
    tool = get_tool(name, context)
    _validate(tool.parameters, arguments, "arguments")
    started = time.perf_counter()
    ok = True
    error = None
    timed_out = False
    timeout_mode = "not_started"
    rate_decision = None
    try:
        rate_decision = enforce_tool_rate_limit(context, name)
        with tool_timeout(tool.timeout_seconds) as timeout_state:
            timeout_mode = str(timeout_state.get("mode") or "unknown")
            payload = tool.handler(context, arguments)
        if not isinstance(payload, dict):
            payload = {"result": payload}
    except AgentToolTimeoutError as exc:
        ok = False
        timed_out = True
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"
        try:
            import frappe
            frappe.db.rollback()
        except Exception:
            pass
        payload = {
            "ok": False,
            "error": error,
            "tool": name,
            "timed_out": True,
        }
    except Exception as exc:
        ok = False
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"
        payload = {"ok": False, "error": error, "tool": name}

    serialised = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    truncated = False
    if len(serialised) > tool.max_output_chars:
        payload = {
            "ok": ok,
            "tool": name,
            "truncated": True,
            "output_prefix": serialised[: tool.max_output_chars],
        }
        serialised = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
        truncated = True

    trace = {
        "tool": name,
        "ok": ok,
        "read_only": tool.read_only,
        "duration_ms": round(
            (time.perf_counter() - started) * 1000,
            2,
        ),
        "output_chars": len(serialised),
        "truncated": truncated,
        "error": error,
        "timed_out": timed_out,
        "timeout_seconds": tool.timeout_seconds,
        "timeout_mode": timeout_mode,
        "rate_limit_current": (
            rate_decision.current if rate_decision else None
        ),
        "rate_limit": (
            rate_decision.limit if rate_decision else None
        ),
    }
    audit_id, audit_logged = audit_tool_execution(
        context=context,
        tool_name=name,
        arguments=arguments,
        output=payload,
        trace=trace,
    )
    trace["audit_id"] = audit_id
    trace["audit_logged"] = audit_logged
    return payload, trace


def registry_probe(context: ToolContext) -> dict[str, Any]:
    tools = available_tools(context)
    definitions = openai_tool_definitions(context)
    return {
        "tool_count": len(tools),
        "tool_names": [tool.name for tool in tools],
        "all_read_only": all(tool.read_only for tool in tools),
        "all_strict": all(
            definition.get("strict") is True
            for definition in definitions
        ),
        "all_object_schemas": all(
            definition.get("parameters", {}).get("type") == "object"
            for definition in definitions
        ),
    }
