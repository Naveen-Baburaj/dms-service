from __future__ import annotations

import json
from typing import Any

import frappe

from dms.rpa.gohighlevel.schemas import RPAValidationError
from dms.rpa.gohighlevel.session import check_session as check_ghl_session
from dms.rpa.gohighlevel.session import connect_session
from dms.rpa.gohighlevel.worker import get_job_status as read_job_status
from dms.rpa.gohighlevel.worker import save_contact as save_contact_worker
from dms.utils.permissions import is_group_admin
from dms.utils.response import error, success


def _header(name: str) -> str | None:
    try:
        return frappe.get_request_header(name)
    except Exception:
        return None


def _is_demo_admin_header() -> bool:
    return _header("x-user-role") == "service_centre_admin"


def _is_tenant_header() -> bool:
    return _header("x-user-role") == "tenant_user"


def _is_real_group_admin() -> bool:
    try:
        return is_group_admin()
    except Exception:
        return False


def _require_rpa_admin():
    if _is_tenant_header():
        return error("GoHighLevel RPA is available only for full admin users.", http_status_code=403)
    if _is_real_group_admin() or _is_demo_admin_header():
        return None
    return error("GoHighLevel RPA is available only for full admin users.", http_status_code=403)


def _request_json() -> dict[str, Any]:
    if frappe.form_dict:
        if frappe.form_dict.get("data"):
            try:
                return json.loads(frappe.form_dict.get("data") or "{}")
            except Exception:
                return {}
        return dict(frappe.form_dict)

    try:
        raw = frappe.request.get_data(as_text=True)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_limit(value: Any, default: int = 25, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(parsed, maximum))


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@frappe.whitelist(allow_guest=True)
def check_session(session_name: str | None = None, deep_check: int | str | bool = False, contacts_url: str | None = None):
    denied = _require_rpa_admin()
    if denied:
        return denied

    payload = _request_json()
    final_session = session_name or payload.get("session_name") or "default"
    final_contacts_url = contacts_url or payload.get("contacts_url")
    final_deep_check = _bool(deep_check or payload.get("deep_check"))

    try:
        data = check_ghl_session(final_session, final_contacts_url, final_deep_check)
        return success(data=data)
    except Exception as exc:
        return error("Failed to check GoHighLevel session.", details=str(exc), http_status_code=500)


@frappe.whitelist(allow_guest=True)
def open_login(session_name: str | None = None, timeout_seconds: int | None = None, contacts_url: str | None = None):
    denied = _require_rpa_admin()
    if denied:
        return denied

    payload = _request_json()
    final_session = session_name or payload.get("session_name") or "default"
    final_contacts_url = contacts_url or payload.get("contacts_url") or payload.get("target_url")
    timeout = timeout_seconds or payload.get("timeout_seconds")

    try:
        data = connect_session(final_session, final_contacts_url, int(timeout) if timeout else None)
        return success(data=data, message="GoHighLevel session connected.")
    except Exception as exc:
        return error("GoHighLevel connection failed.", details=str(exc), http_status_code=400)


@frappe.whitelist(allow_guest=True)
def save_contact(target: str | None = None, contact: str | dict[str, Any] | None = None, contacts_url: str | None = None, session_name: str | None = None):
    denied = _require_rpa_admin()
    if denied:
        return denied

    payload = _request_json()
    final_target = target or payload.get("target") or "both"
    final_session = session_name or payload.get("session_name") or "default"
    final_contacts_url = contacts_url or payload.get("contacts_url")

    raw_contact = contact if contact is not None else payload.get("contact") or payload
    if isinstance(raw_contact, str):
        try:
            raw_contact = json.loads(raw_contact)
        except Exception:
            return error("Invalid contact JSON payload.", http_status_code=400)

    try:
        data = save_contact_worker(
            contact_data=raw_contact,
            target=final_target,
            contacts_url=final_contacts_url,
            session_name=final_session,
        )
        return success(data=data, message=data.get("message") or "Contact saved.")
    except RPAValidationError as exc:
        return error(str(exc), http_status_code=400)
    except Exception as exc:
        return error("Failed to save contact through GoHighLevel RPA module.", details=str(exc), http_status_code=500)


@frappe.whitelist(allow_guest=True)
def list_contacts(limit: int | str | None = None, search: str | None = None):
    denied = _require_rpa_admin()
    if denied:
        return denied

    payload = _request_json()
    final_limit = _int_limit(limit or payload.get("limit"), default=25, maximum=100)
    final_search = _string_or_none(search or payload.get("search"))

    fields = [
        "name",
        "contact_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "vehicle_interest",
        "source",
        "save_target",
        "ghl_tag",
        "ghl_sync_status",
        "ghl_sync_message",
        "ghl_contact_url",
        "rpa_job",
        "last_synced_at",
        "modified",
    ]

    or_filters = None
    if final_search:
        like = f"%{final_search}%"
        or_filters = [
            ["DMS CRM Contact", "name", "like", like],
            ["DMS CRM Contact", "contact_name", "like", like],
            ["DMS CRM Contact", "email", "like", like],
            ["DMS CRM Contact", "phone", "like", like],
            ["DMS CRM Contact", "rpa_job", "like", like],
        ]

    try:
        rows = frappe.get_all(
            "DMS CRM Contact",
            fields=fields,
            or_filters=or_filters,
            order_by="modified desc",
            limit_page_length=final_limit,
        )
        return success(data={"rows": rows, "total": len(rows), "limit": final_limit, "search": final_search})
    except Exception as exc:
        return error("Failed to list saved RPA contacts.", details=str(exc), http_status_code=500)


@frappe.whitelist(allow_guest=True)
def get_job_status(job_id: str | None = None):
    denied = _require_rpa_admin()
    if denied:
        return denied

    payload = _request_json()
    final_job_id = job_id or payload.get("job_id") or payload.get("name")
    if not final_job_id:
        return error("job_id is required.", http_status_code=400)

    try:
        return success(data=read_job_status(final_job_id))
    except Exception as exc:
        return error("Failed to read RPA job status.", details=str(exc), http_status_code=404)


@frappe.whitelist(allow_guest=True)
def module_info():
    denied = _require_rpa_admin()
    if denied:
        return denied

    return success(
        data={
            "module": "GoHighLevel RPA",
            "provider": "GoHighLevel",
            "demo_tag": "dms_rpa_demo",
            "targets": ["dms", "ghl", "both"],
            "endpoints": {
                "check_session": "/api/method/dms.api.rpa_gohighlevel.check_session",
                "open_login": "/api/method/dms.api.rpa_gohighlevel.open_login",
                "save_contact": "/api/method/dms.api.rpa_gohighlevel.save_contact",
                "list_contacts": "/api/method/dms.api.rpa_gohighlevel.list_contacts",
                "get_job_status": "/api/method/dms.api.rpa_gohighlevel.get_job_status",
            },
            "notes": [
                "Admin-only module.",
                "The DMS contact can be saved locally, in GoHighLevel, or in both.",
                "Tenant users are denied at the backend boundary.",
            ],
        }
    )
