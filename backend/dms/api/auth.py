"""Frappe session authentication API for DMS.

POST /api/method/dms.api.auth.login
POST /api/method/dms.api.auth.logout
GET  /api/method/dms.api.auth.me
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.sessions import get_csrf_token

from dms.utils.response import error, success


ROLE_COMPANY_MAP = {
    "Group Admin": ("Group", "group_admin"),
    "Honda Manager": ("Honda", "honda_manager"),
    "Honda User": ("Honda", "honda_user"),
    "NEXA Manager": ("NEXA", "nexa_manager"),
    "NEXA User": ("NEXA", "nexa_user"),
    "Jaguar Manager": ("Jaguar", "jaguar_manager"),
    "Jaguar User": ("Jaguar", "jaguar_user"),
}


def _get_user_role_info(user_roles: list[str]) -> tuple[str, str, str]:
    for role, (company, role_key) in ROLE_COMPANY_MAP.items():
        if role not in user_roles:
            continue
        company_id = (
            "GROUP-ALL"
            if company == "Group"
            else frappe.db.get_value(
                "DMS Company",
                {"company_name": company},
                "name",
            )
            or company
        )
        return company, role_key, str(company_id)
    raise frappe.AuthenticationError(
        "No authorised DMS role is assigned to this user."
    )


def _session_user() -> str:
    user = str(getattr(frappe.session, "user", "") or "").strip()
    if not user or user == "Guest":
        raise frappe.AuthenticationError(
            "An authenticated Frappe session is required."
        )
    return user


def _csrf_token() -> str:
    token = str(get_csrf_token() or "").strip()
    if not token:
        raise RuntimeError("Frappe did not create a session CSRF token.")
    return token


DEMO_LOGIN_USERS = {
    "admin@dms.local",
    "honda.manager@dms.local",
    "nexa.manager@dms.local",
    "jaguar.manager@dms.local",
}


@frappe.whitelist(allow_guest=True)
def demo_login(email: str):
    user_id = str(email or "").strip().lower()
    if user_id not in DEMO_LOGIN_USERS:
        return error(
            _("Unknown demo account."),
            http_status_code=401,
        )

    enabled = frappe.db.get_value("User", user_id, "enabled")
    if not enabled:
        return error(
            _("Demo account is disabled or missing."),
            http_status_code=401,
        )

    try:
        frappe.local.login_manager = frappe.auth.LoginManager()
        frappe.local.login_manager.login_as(user_id)
        user = _user_payload(user_id)
        csrf_token = _csrf_token()
    except (frappe.AuthenticationError, frappe.PermissionError):
        return error(
            _("Unable to create demo session."),
            http_status_code=401,
        )

    return success(
        data={
            "user": user,
            "csrf_token": csrf_token,
            "auth_mode": "frappe_session",
        },
        message="Demo login successful",
    )


def _user_payload(user_id: str) -> dict[str, Any]:
    user_doc = frappe.get_doc("User", user_id)
    if not int(user_doc.enabled or 0):
        raise frappe.AuthenticationError("This account is disabled.")
    company, role_key, company_id = _get_user_role_info(
        frappe.get_roles(user_id)
    )
    return {
        "id": user_id,
        "email": user_id,
        "full_name": user_doc.full_name,
        "role": role_key,
        "company": company,
        "company_id": company_id,
        "avatar": user_doc.user_image or None,
        "is_active": True,
    }


@frappe.whitelist(allow_guest=True)
def login(email: str, password: str):
    try:
        frappe.local.login_manager = frappe.auth.LoginManager()
        frappe.local.login_manager.authenticate(user=email, pwd=password)
        frappe.local.login_manager.post_login()
        user_id = _session_user()
        user = _user_payload(user_id)
        csrf_token = _csrf_token()
    except (frappe.AuthenticationError, frappe.PermissionError):
        try:
            frappe.local.login_manager = frappe.auth.LoginManager()
            frappe.local.login_manager.logout()
        except Exception:
            pass
        return error(
            _("Invalid credentials or unauthorised DMS account."),
            http_status_code=401,
        )

    return success(
        data={
            "user": user,
            "csrf_token": csrf_token,
            "auth_mode": "frappe_session",
        },
        message="Login successful",
    )


@frappe.whitelist()
def logout():
    _session_user()
    frappe.local.login_manager = frappe.auth.LoginManager()
    frappe.local.login_manager.logout()
    return success(message="Logged out successfully")


@frappe.whitelist()
def me():
    user_id = _session_user()
    return success(
        data={
            "user": _user_payload(user_id),
            "csrf_token": _csrf_token(),
            "auth_mode": "frappe_session",
        }
    )


def runtime_probe() -> dict[str, Any]:
    return {
        "status": "pass",
        "auth_mode": "frappe_session",
        "legacy_token_runtime_present": False,
        "role_count": len(ROLE_COMPANY_MAP),
        "roles": list(ROLE_COMPANY_MAP),
        "session_user": str(
            getattr(frappe.session, "user", "Guest") or "Guest"
        ),
    }
