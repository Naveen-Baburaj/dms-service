"""
JWT Authentication API for DMS.

POST /api/method/dms.api.auth.login
POST /api/method/dms.api.auth.logout
POST /api/method/dms.api.auth.refresh
GET  /api/method/dms.api.auth.me
"""

import frappe
import jwt
import datetime
from frappe import _
from dms.utils.response import success, error

JWT_SECRET = frappe.conf.get("jwt_secret", "change-this-in-production-min-32-chars")
ACCESS_TOKEN_EXPIRES = datetime.timedelta(hours=8)
REFRESH_TOKEN_EXPIRES = datetime.timedelta(days=30)
ALGORITHM = "HS256"

ROLE_COMPANY_MAP = {
    "Honda User":    ("Honda", "honda_user"),
    "Honda Manager": ("Honda", "honda_manager"),
    "NEXA User":     ("NEXA", "nexa_user"),
    "NEXA Manager":  ("NEXA", "nexa_manager"),
    "Jaguar User":   ("Jaguar", "jaguar_user"),
    "Jaguar Manager":("Jaguar", "jaguar_manager"),
    "Group Admin":   ("Group", "group_admin"),
}


def _get_user_role_info(user_roles: list[str]) -> tuple[str, str, str]:
    """Return (company, role, company_id) for a user."""
    for role, (company, role_key) in ROLE_COMPANY_MAP.items():
        if role in user_roles:
            company_id = frappe.db.get_value(
                "DMS Company", {"company_name": company}, "name"
            ) or company
            return company, role_key, company_id
    frappe.throw(_("No valid DMS role assigned to this user."), frappe.AuthenticationError)


def _generate_tokens(user_id: str, user_doc) -> dict:
    user_roles = frappe.get_roles(user_id)
    company, role_key, company_id = _get_user_role_info(user_roles)

    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "email": user_doc.email,
        "full_name": user_doc.full_name,
        "role": role_key,
        "company": company,
        "company_id": company_id,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRES,
    }

    access_token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

    refresh_payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + REFRESH_TOKEN_EXPIRES,
    }
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=ALGORITHM)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": int(ACCESS_TOKEN_EXPIRES.total_seconds()),
        "token_type": "Bearer",
    }


@frappe.whitelist(allow_guest=True)
def login(email: str, password: str):
    try:
        frappe.local.login_manager = frappe.auth.LoginManager()
        frappe.local.login_manager.authenticate(user=email, pwd=password)
        frappe.local.login_manager.post_login()
    except frappe.AuthenticationError:
        return error(_("Invalid email or password."), http_status_code=401)

    user_doc = frappe.get_doc("User", email)
    if user_doc.enabled == 0:
        return error(_("Your account has been disabled. Contact your administrator."), 403)

    tokens = _generate_tokens(email, user_doc)
    user_roles = frappe.get_roles(email)
    company, role_key, company_id = _get_user_role_info(user_roles)

    return success(
        data={
            "user": {
                "id": email,
                "email": email,
                "full_name": user_doc.full_name,
                "role": role_key,
                "company": company,
                "company_id": company_id,
                "avatar": user_doc.user_image or None,
                "is_active": True,
            },
            "tokens": tokens,
        },
        message="Login successful",
    )


@frappe.whitelist()
def logout():
    frappe.local.login_manager = frappe.auth.LoginManager()
    frappe.local.login_manager.logout()
    return success(message="Logged out successfully")


@frappe.whitelist(allow_guest=True)
def refresh(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id = payload["sub"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return error(_("Invalid or expired refresh token."), http_status_code=401)

    user_doc = frappe.get_doc("User", user_id)
    if user_doc.enabled == 0:
        return error(_("Account disabled."), 403)

    tokens = _generate_tokens(user_id, user_doc)
    return success(
        data={
            "access_token": tokens["access_token"],
            "expires_in": tokens["expires_in"],
        }
    )


@frappe.whitelist()
def me():
    user_id = frappe.session.user
    user_doc = frappe.get_doc("User", user_id)
    user_roles = frappe.get_roles(user_id)
    company, role_key, company_id = _get_user_role_info(user_roles)

    return success(
        data={
            "id": user_id,
            "email": user_id,
            "full_name": user_doc.full_name,
            "role": role_key,
            "company": company,
            "company_id": company_id,
            "avatar": user_doc.user_image or None,
            "is_active": True,
        }
    )


def authenticate_jwt():
    """Hook called by Frappe on each request to validate JWT Bearer tokens."""
    authorization = frappe.get_request_header("Authorization", "")
    if not authorization.startswith("Bearer "):
        return

    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        frappe.set_user(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        frappe.throw(_("Invalid or expired token."), frappe.AuthenticationError)
