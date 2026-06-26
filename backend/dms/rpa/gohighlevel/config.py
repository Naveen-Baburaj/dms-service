from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import frappe


DEFAULT_GHL_LOGIN_URL = "https://app.gohighlevel.com/?logout=true"
DEFAULT_GHL_TAG_NAME = "dms_rpa_demo"
DEFAULT_SESSION_NAME = "default"


def _conf(name: str, default: Any = None) -> Any:
    """Read config from Frappe site_config first, then environment variables."""
    try:
        value = frappe.conf.get(name)
        if value not in (None, ""):
            return value
    except Exception:
        pass

    value = os.getenv(name)
    if value not in (None, ""):
        return value

    lower_value = os.getenv(name.lower())
    if lower_value not in (None, ""):
        return lower_value

    return default


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_session_name(session_name: str | None = None) -> str:
    raw = (session_name or DEFAULT_SESSION_NAME).strip() or DEFAULT_SESSION_NAME
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", raw)
    return cleaned[:80] or DEFAULT_SESSION_NAME


def rpa_base_dir(provider: str = "gohighlevel") -> Path:
    """Return a private runtime directory for browser sessions/screenshots."""
    try:
        base = Path(frappe.get_site_path("private", "rpa_sessions", provider))
    except Exception:
        base = Path.cwd() / ".rpa_sessions" / provider

    base.mkdir(parents=True, exist_ok=True)
    return base


def storage_state_path(session_name: str | None = None) -> Path:
    session = safe_session_name(session_name)
    return rpa_base_dir() / f"{session}.storage_state.json"


def screenshot_dir(session_name: str | None = None) -> Path:
    session = safe_session_name(session_name)
    path = rpa_base_dir() / "screenshots" / session
    path.mkdir(parents=True, exist_ok=True)
    return path


def ghl_login_url() -> str:
    return str(_conf("GHL_LOGIN_URL", DEFAULT_GHL_LOGIN_URL))


def ghl_contacts_url() -> str | None:
    """Configured Smart List URL for DMS RPA Demo Contacts."""
    value = _conf("GHL_CONTACTS_URL", None)
    return str(value).strip() if value else None


def ghl_tag_name() -> str:
    return str(_conf("GHL_RPA_TAG_NAME", DEFAULT_GHL_TAG_NAME)).strip() or DEFAULT_GHL_TAG_NAME


def ghl_tag_search_text() -> str:
    return str(_conf("GHL_RPA_TAG_SEARCH_TEXT", "dms")).strip() or "dms"


def playwright_headless() -> bool:
    # Demo default is headed/browser-visible.
    return _bool(_conf("GHL_RPA_HEADLESS", "false"), default=False)


def playwright_slow_mo_ms() -> int:
    # Small delay makes the demo visually understandable without making it too slow.
    return _int(_conf("GHL_RPA_SLOW_MO_MS", 150), 150)


def operation_timeout_ms() -> int:
    return _int(_conf("GHL_RPA_TIMEOUT_MS", 45000), 45000)


def login_timeout_seconds() -> int:
    return _int(_conf("GHL_RPA_LOGIN_TIMEOUT_SECONDS", 300), 300)
