from __future__ import annotations

import secrets
from typing import Any

import frappe

from dms.api.seed_demo_data_v2 import seed as seed_baseline
from dms.api.seed_rich_demo_data import run as seed_rich_data
from dms.auth_setup import LOCAL_USER_SPECS, _provision_user


EXPECTED_COUNTS = {
    "DMS Company": 3,
    "DMS Lead": 339,
    "DMS Customer": 45,
    "DMS Vehicle": 104,
    "DMS Vehicle Sale": 339,
    "DMS Test Drive": 222,
    "DMS Booking": 222,
    "DMS Service Job": 1571,
    "DMS Invoice": 330,
}

EXPECTED_INVENTORY = {
    "Honda": 38,
    "NEXA": 33,
    "Jaguar": 33,
}


def _census() -> dict[str, int]:
    return {
        doctype: int(frappe.db.count(doctype) or 0)
        for doctype in EXPECTED_COUNTS
    }


def _inventory() -> dict[str, int]:
    return {
        company: int(
            frappe.db.count("DMS Vehicle", {"company_id": company}) or 0
        )
        for company in EXPECTED_INVENTORY
    }


def run() -> dict[str, Any]:
    """Create and verify the deterministic Railway demo database once."""

    baseline = seed_baseline()
    rich = seed_rich_data()

    users = []
    for email in LOCAL_USER_SPECS:
        users.append(
            _provision_user(
                email,
                secrets.token_urlsafe(32),
            )
        )

    frappe.db.commit()

    census = _census()
    inventory = _inventory()
    census_mismatch = {
        doctype: {"expected": expected, "actual": census.get(doctype)}
        for doctype, expected in EXPECTED_COUNTS.items()
        if census.get(doctype) != expected
    }
    inventory_mismatch = {
        company: {"expected": expected, "actual": inventory.get(company)}
        for company, expected in EXPECTED_INVENTORY.items()
        if inventory.get(company) != expected
    }

    if census_mismatch or inventory_mismatch:
        raise AssertionError(
            {
                "census_mismatch": census_mismatch,
                "inventory_mismatch": inventory_mismatch,
            }
        )

    return {
        "status": "pass",
        "baseline": baseline,
        "rich": rich,
        "census": census,
        "inventory": inventory,
        "demo_users": [
            {"email": row["email"], "role": row["role"]}
            for row in users
        ],
        "passwords_returned": False,
    }
