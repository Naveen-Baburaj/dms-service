from __future__ import annotations

import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import frappe

from .config import (
    ghl_contacts_url,
    ghl_login_url,
    login_timeout_seconds,
    operation_timeout_ms,
    playwright_headless,
    playwright_slow_mo_ms,
    safe_session_name,
    screenshot_dir,
    storage_state_path,
)
from .schemas import GHLLoginRequired


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception as exc:
        raise RuntimeError(
            "Playwright is not installed in the Frappe environment. "
            f"Frappe Python: {sys.executable}. "
            "Install it into the bench virtualenv with: "
            "frappe-bench/env/bin/python -m pip install playwright && "
            "PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 frappe-bench/env/bin/python -m playwright install chromium"
        ) from exc


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _as_str_path(path: Path | None) -> str | None:
    return str(path) if path else None


def _upsert_session_doc(
    session_name: str,
    status: str,
    message: str = "",
    contacts_url: str | None = None,
    storage_path: Path | None = None,
) -> None:
    if not frappe.db.exists("DocType", "DMS GHL Session"):
        return

    name = frappe.db.get_value("DMS GHL Session", {"session_name": session_name}, "name")
    doc = frappe.get_doc("DMS GHL Session", name) if name else frappe.new_doc("DMS GHL Session")
    if not name:
        doc.session_name = session_name

    doc.status = status
    doc.last_message = message
    doc.last_checked_at = _now()
    if contacts_url:
        doc.contacts_url = contacts_url
    if storage_path:
        doc.storage_state_path = _as_str_path(storage_path)
    if status == "Active":
        doc.last_login_at = _now()
    doc.save(ignore_permissions=True)


def is_probably_connected(page) -> bool:
    url = (page.url or "").lower()
    if "app.gohighlevel.com" not in url:
        return False
    if "/v2/" in url:
        return True
    try:
        return page.get_by_text("Contacts", exact=True).count() > 0
    except Exception:
        return False


# Backward-compatible alias used by skills.py.
is_probably_logged_in = is_probably_connected


def session_file_exists(session_name: str | None = None) -> bool:
    return storage_state_path(session_name).exists()


def check_session(session_name: str | None = None, contacts_url: str | None = None, deep_check: bool = False) -> dict[str, Any]:
    session = safe_session_name(session_name)
    storage_path = storage_state_path(session)
    configured_url = contacts_url or ghl_contacts_url()

    data = {
        "session_name": session,
        "status": "Active" if storage_path.exists() else "Login Required",
        "storage_state_exists": storage_path.exists(),
        "storage_state_path": str(storage_path),
        "contacts_url": configured_url,
        "deep_check": bool(deep_check),
    }

    if not deep_check:
        _upsert_session_doc(
            session_name=session,
            status=data["status"],
            message="Saved browser state exists." if storage_path.exists() else "No saved browser state exists.",
            contacts_url=configured_url,
            storage_path=storage_path if storage_path.exists() else None,
        )
        return data

    if not storage_path.exists():
        _upsert_session_doc(session, "Login Required", "No saved browser state exists.", configured_url)
        return data

    sync_playwright = _require_playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()
        try:
            page.goto(configured_url or "https://app.gohighlevel.com/v2/", wait_until="domcontentloaded", timeout=operation_timeout_ms())
            page.wait_for_timeout(1500)
            active = is_probably_connected(page)
            data["status"] = "Active" if active else "Login Required"
            data["current_url"] = page.url
            _upsert_session_doc(
                session,
                data["status"],
                "Deep browser-state check completed.",
                configured_url,
                storage_path if active else None,
            )
        finally:
            context.close()
            browser.close()

    return data


def connect_session(
    session_name: str | None = None,
    target_url: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    session = safe_session_name(session_name)
    timeout = int(timeout_seconds or login_timeout_seconds())
    storage_path = storage_state_path(session)
    screenshot_path = screenshot_dir(session) / f"connect_success_{int(time.time())}.png"
    configured_url = target_url or ghl_contacts_url()

    sync_playwright = _require_playwright()

    with sync_playwright() as p:
        # Login must stay visible for the admin/security-code flow. The actual save/sync worker still uses GHL_RPA_HEADLESS.
        browser = p.chromium.launch(headless=False, slow_mo=playwright_slow_mo_ms())
        context = browser.new_context()
        page = context.new_page()
        page.goto(ghl_login_url(), wait_until="domcontentloaded", timeout=operation_timeout_ms())

        deadline = time.monotonic() + timeout
        last_url = page.url

        while time.monotonic() < deadline:
            try:
                last_url = page.url
                if is_probably_connected(page):
                    if configured_url:
                        try:
                            page.goto(configured_url, wait_until="domcontentloaded", timeout=operation_timeout_ms())
                            page.wait_for_timeout(1000)
                        except Exception:
                            pass

                    context.storage_state(path=str(storage_path))
                    try:
                        page.screenshot(path=str(screenshot_path), full_page=True)
                    except Exception:
                        screenshot_path = None

                    _upsert_session_doc(
                        session_name=session,
                        status="Active",
                        message="Browser connection completed and state was saved.",
                        contacts_url=configured_url,
                        storage_path=storage_path,
                    )

                    current_url = page.url
                    context.close()
                    browser.close()
                    return {
                        "session_name": session,
                        "status": "Active",
                        "storage_state_path": str(storage_path),
                        "contacts_url": configured_url,
                        "current_url": current_url,
                        "screenshot": _as_str_path(screenshot_path),
                        "message": "GoHighLevel browser state saved successfully.",
                    }
            except Exception:
                pass
            page.wait_for_timeout(1000)

        context.close()
        browser.close()

    _upsert_session_doc(session, "Login Required", f"Connection was not completed within {timeout} seconds.", configured_url)
    raise GHLLoginRequired(
        f"GoHighLevel browser connection was not completed within {timeout} seconds. Last observed URL: {last_url}"
    )
