from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.utils.password import update_password


LOCAL_USER_SPECS = {
    "admin@dms.local": {
        "full_name": "DMS Group Administrator",
        "role": "Group Admin",
    },
    "honda.manager@dms.local": {
        "full_name": "Honda Manager",
        "role": "Honda Manager",
    },
    "nexa.manager@dms.local": {
        "full_name": "NEXA Manager",
        "role": "NEXA Manager",
    },
    "jaguar.manager@dms.local": {
        "full_name": "Jaguar Manager",
        "role": "Jaguar Manager",
    },
}

DMS_ROLES = frozenset(
    {
        "Group Admin",
        "Honda Manager",
        "Honda User",
        "NEXA Manager",
        "NEXA User",
        "Jaguar Manager",
        "Jaguar User",
    }
)
EXPECTED_COMPANIES = frozenset({"Honda", "NEXA", "Jaguar"})


def _credentials(path_value: str) -> list[dict[str, str]]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Credential input does not exist: {path}")
    data = json.loads(path.read_text())
    rows = data.get("users") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Credential input must contain a users list")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every credential entry must be an object")
        email = str(row.get("email") or "").strip().lower()
        password = str(row.get("password") or "")
        if email not in LOCAL_USER_SPECS:
            raise ValueError(f"Unexpected local DMS user: {email}")
        if email in seen:
            raise ValueError(f"Duplicate local DMS user: {email}")
        if len(password) < 20:
            raise ValueError(f"Password is too short for {email}")
        seen.add(email)
        result.append({"email": email, "password": password})

    if seen != set(LOCAL_USER_SPECS):
        missing = sorted(set(LOCAL_USER_SPECS) - seen)
        raise ValueError(f"Missing local DMS credentials: {missing}")
    return result


def _user_state(email: str) -> dict[str, Any]:
    spec = LOCAL_USER_SPECS[email]
    exists = bool(frappe.db.exists("User", email))
    roles = set(frappe.get_roles(email)) if exists else set()
    dms_roles = sorted(roles & DMS_ROLES)
    return {
        "email": email,
        "exists": exists,
        "enabled": bool(
            frappe.db.get_value("User", email, "enabled")
            if exists
            else False
        ),
        "expected_role": spec["role"],
        "role_present": spec["role"] in roles,
        "dms_roles": dms_roles,
        "exact_dms_role": dms_roles == [spec["role"]],
    }


def preflight_probe() -> dict[str, Any]:
    from frappe.utils.background_jobs import get_redis_conn

    assert frappe.db.sql("select 1")[0][0] == 1
    assert frappe.cache().ping() is True
    assert get_redis_conn().ping() is True

    role_exists = {
        role: bool(frappe.db.exists("Role", role))
        for role in sorted(DMS_ROLES)
    }
    if not all(role_exists.values()):
        missing = [role for role, exists in role_exists.items() if not exists]
        raise AssertionError(f"Missing DMS roles: {missing}")

    companies = {
        str(row.company_name): str(row.name)
        for row in frappe.get_all(
            "DMS Company",
            fields=["name", "company_name"],
            limit_page_length=100,
        )
    }
    missing_companies = sorted(EXPECTED_COMPANIES - set(companies))
    if missing_companies:
        raise AssertionError(f"Missing DMS companies: {missing_companies}")

    return {
        "status": "pass",
        "database": True,
        "redis_cache": True,
        "redis_queue": True,
        "role_exists": role_exists,
        "companies": companies,
        "users": [_user_state(email) for email in LOCAL_USER_SPECS],
    }


def _provision_user(email: str, password: str) -> dict[str, Any]:
    spec = LOCAL_USER_SPECS[email]
    created = not frappe.db.exists("User", email)

    if created:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": spec["full_name"],
                "enabled": 1,
                "user_type": "System User",
                "send_welcome_email": 0,
            }
        )
        user.insert(ignore_permissions=True)
    else:
        user = frappe.get_doc("User", email)
        user.enabled = 1
        user.first_name = spec["full_name"]
        user.user_type = "System User"
        user.send_welcome_email = 0
        user.save(ignore_permissions=True)

    current_roles = set(frappe.get_roles(email))
    unexpected = sorted(
        (current_roles & DMS_ROLES) - {spec["role"]}
    )
    if unexpected:
        user.remove_roles(*unexpected)
        user.reload()

    if spec["role"] not in set(frappe.get_roles(email)):
        user.add_roles(spec["role"])
        user.reload()

    update_password(user=email, pwd=password, logout_all_sessions=True)

    final_state = _user_state(email)
    if not (
        final_state["exists"]
        and final_state["enabled"]
        and final_state["exact_dms_role"]
    ):
        raise AssertionError(
            f"Provisioned user does not have the exact DMS role: {final_state}"
        )

    return {
        "email": email,
        "role": spec["role"],
        "created": created,
        "enabled": True,
        "removed_conflicting_dms_roles": unexpected,
    }


def provision_local_users(credentials_path: str) -> dict[str, Any]:
    rows = _credentials(credentials_path)
    provisioned = [
        _provision_user(row["email"], row["password"])
        for row in rows
    ]
    frappe.db.commit()
    return {
        "status": "pass",
        "provisioned": provisioned,
        "passwords_returned": False,
    }


def worker_probe() -> dict[str, Any]:
    from frappe.utils.background_jobs import get_workers

    workers = list(get_workers())
    return {
        "status": "pass",
        "worker_count": len(workers),
        "workers": [
            {
                "name": str(getattr(worker, "name", "") or ""),
                "state": str(getattr(worker, "state", "") or ""),
            }
            for worker in workers
        ],
    }


def runtime_probe() -> dict[str, Any]:
    preflight = preflight_probe()
    users = [_user_state(email) for email in LOCAL_USER_SPECS]
    if not all(
        item["exists"]
        and item["enabled"]
        and item["role_present"]
        and item["exact_dms_role"]
        for item in users
    ):
        raise AssertionError(
            "One or more local DMS users are not provisioned with an exact role"
        )
    return {
        "status": "pass",
        "dependencies": {
            "database": preflight["database"],
            "redis_cache": preflight["redis_cache"],
            "redis_queue": preflight["redis_queue"],
        },
        "users": users,
    }
