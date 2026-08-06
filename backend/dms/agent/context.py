from __future__ import annotations

import uuid

import frappe

from dms.agent.types import ToolContext
from dms.utils.permissions import get_user_company, is_group_admin


ROLE_KEYS = {
    "Group Admin": "group_admin",
    "Honda Manager": "honda_manager",
    "Honda User": "honda_user",
    "NEXA Manager": "nexa_manager",
    "NEXA User": "nexa_user",
    "Jaguar Manager": "jaguar_manager",
    "Jaguar User": "jaguar_user",
}


def _header(name: str) -> str:
    try:
        return str(frappe.get_request_header(name) or "").strip()
    except Exception:
        return ""


def _session_user() -> str:
    try:
        user = str(frappe.session.user or "").strip()
    except Exception:
        user = ""
    if not user or user == "Guest":
        raise frappe.AuthenticationError(
            "An authenticated Frappe session is required."
        )
    return user


def _role_key(user: str) -> str:
    roles = set(frappe.get_roles(user))
    for role, key in ROLE_KEYS.items():
        if role in roles:
            return key
    raise frappe.PermissionError(
        "The authenticated user does not have an authorised DMS role."
    )


def build_tool_context() -> ToolContext:
    user = _session_user()
    role = _role_key(user)
    is_admin = bool(is_group_admin())

    company_id: str | None = None
    company_name: str | None = None
    if not is_admin:
        resolved = get_user_company()
        if not resolved or resolved == "__none__":
            raise frappe.PermissionError(
                "The authenticated DMS role is not mapped to a company."
            )
        company_id = str(resolved)
        company_name = str(
            frappe.db.get_value(
                "DMS Company",
                company_id,
                "company_name",
            )
            or company_id
        )

    try:
        guarded_request_id = str(
            getattr(frappe.local, "dms_agent_request_id", "") or ""
        ).strip()
    except Exception:
        guarded_request_id = ""

    request_id = (
        guarded_request_id
        or _header("x-client-request-id")
        or _header("x-request-id")
        or str(uuid.uuid4())
    )

    return ToolContext(
        request_id=request_id,
        user=user,
        role=role,
        tenant_id=company_id,
        is_admin=is_admin,
        company_id=company_id,
        company_name=company_name,
    )
