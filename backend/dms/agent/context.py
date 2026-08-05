from __future__ import annotations

import uuid

import frappe

from dms.agent.types import ToolContext


def _header(name: str) -> str:
    try:
        return str(frappe.get_request_header(name) or "").strip()
    except Exception:
        return ""


def build_tool_context() -> ToolContext:
    from dms.api import ai_agent

    is_admin, company_id, company_name = (
        ai_agent._data_agent_current_scope()
    )

    try:
        user = str(frappe.session.user or "Guest").strip() or "Guest"
    except Exception:
        user = "Guest"

    header_role = _header("x-user-role")
    role = header_role or (
        "group_admin" if is_admin else "tenant_user"
    )

    tenant_id = _header("x-tenant-id") or None
    request_id = (
        _header("x-client-request-id")
        or _header("x-request-id")
        or str(uuid.uuid4())
    )

    return ToolContext(
        request_id=request_id,
        user=user,
        role=role,
        tenant_id=tenant_id,
        is_admin=bool(is_admin),
        company_id=str(company_id) if company_id else None,
        company_name=str(company_name) if company_name else None,
    )
