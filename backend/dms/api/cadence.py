"""Secure, role-aware launch handoff to the Cadence voice dashboard."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlsplit, urlunsplit

import frappe

from dms.api.auth import _session_user, _user_payload
from dms.utils.response import success


_ISSUER = "dms-service"
_AUDIENCE = "cadence-dashboard"
_DEFAULT_TTL_SECONDS = 120
_MAX_TTL_SECONDS = 300

_CADENCE_TARGETS = {
    "Group": {"scope": "admin"},
    "Honda": {
        "scope": "tenant",
        "tenant_id": "7fc63bbf-d01c-4b3c-a28f-121b7c93bdeb",
        "tenant_slug": "monster_tree",
    },
    "NEXA": {
        "scope": "tenant",
        "tenant_id": "8cb45aea-1279-4861-b056-e9f10f12bc96",
        "tenant_slug": "bluestack",
    },
    "Jaguar": {
        "scope": "tenant",
        "tenant_id": "bcd3533f-9a62-4713-8ef4-f39814405f82",
        "tenant_slug": "microworld",
    },
}


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _cadence_secret() -> bytes:
    secret = os.getenv("CADENCE_SSO_SECRET", "").encode("utf-8")
    if len(secret) < 32:
        raise RuntimeError("CADENCE_SSO_SECRET must contain at least 32 characters.")
    return secret


def _cadence_launch_url() -> str:
    configured = os.getenv("CADENCE_DASHBOARD_URL", "").strip().rstrip("/")
    parsed = urlsplit(configured)
    is_local = parsed.hostname in {"localhost", "127.0.0.1"}
    if (
        not parsed.hostname
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in ({"http", "https"} if is_local else {"https"})
    ):
        raise RuntimeError(
            "CADENCE_DASHBOARD_URL must be an HTTPS origin (HTTP is allowed locally)."
        )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _launch_ttl_seconds() -> int:
    try:
        configured = int(os.getenv("CADENCE_SSO_TTL_SECONDS", _DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        configured = _DEFAULT_TTL_SECONDS
    return max(30, min(configured, _MAX_TTL_SECONDS))


def _create_launch_token(
    user_id: str,
    company: str,
    role: str,
) -> tuple[str, int, dict[str, str]]:
    target = _CADENCE_TARGETS.get(company)
    if target is None:
        raise frappe.PermissionError("This DMS account has no Cadence workspace.")

    now = int(time.time())
    ttl_seconds = _launch_ttl_seconds()
    payload = {
        "v": 1,
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": user_id,
        "scope": target["scope"],
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
        "nonce": secrets.token_urlsafe(24),
    }
    if target["scope"] == "tenant":
        payload["tenant_id"] = target["tenant_id"]
        payload["tenant_slug"] = target["tenant_slug"]

    encoded_payload = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        _cadence_secret(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_b64encode(signature)}", ttl_seconds, target


@frappe.whitelist()
def launch():
    """Create a one-time, short-lived Cadence dashboard handoff."""

    user_id = _session_user()
    user = _user_payload(user_id)
    token, expires_in, target = _create_launch_token(
        user_id,
        user["company"],
        user["role"],
    )

    return success(
        data={
            "launch_url": f"{_cadence_launch_url()}/dashboard/sso",
            "token": token,
            "expires_in": expires_in,
            "scope": target["scope"],
            "tenant_slug": target.get("tenant_slug"),
        },
        message="Cadence launch authorised",
    )
