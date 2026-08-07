from __future__ import annotations

from collections import Counter
from typing import Any

import frappe

from dms.utils.permissions import get_user_company, is_group_admin
from dms.utils.response import success


# DMS_DEMO_INVENTORY_V1
VEHICLE_FIELDS = [
    "name",
    "company_id",
    "vehicle_name",
    "model",
    "variant",
    "color",
    "year",
    "fuel_type",
    "transmission",
    "chassis_no",
    "engine_no",
    "ex_showroom_price",
    "on_road_price",
    "stock_status",
    "image",
]


def _session_user() -> str:
    user = str(getattr(frappe.session, "user", "") or "").strip()
    if not user or user == "Guest":
        raise frappe.AuthenticationError(
            "An authenticated DMS session is required."
        )
    return user


def _inventory_payload() -> dict[str, Any]:
    user = _session_user()
    admin = bool(is_group_admin())

    company_id: str | None = None
    if not admin:
        resolved = get_user_company()
        if not resolved or resolved == "__none__":
            raise frappe.PermissionError(
                "The authenticated user is not mapped to a DMS company."
            )
        company_id = str(resolved)

    filters: dict[str, Any] = {}
    if company_id:
        filters["company_id"] = company_id

    meta = frappe.get_meta("DMS Vehicle")
    existing_fields = {
        str(field.fieldname)
        for field in meta.fields
        if field.fieldname
    }
    required_fields = {
        "company_id",
        "vehicle_name",
        "model",
        "variant",
        "color",
        "stock_status",
    }
    missing_required = sorted(required_fields - existing_fields)
    if missing_required:
        raise RuntimeError(
            "DMS Vehicle schema is missing required inventory fields: "
            + ", ".join(missing_required)
        )

    selected_fields = ["name"] + [
        field
        for field in VEHICLE_FIELDS
        if field != "name" and field in existing_fields
    ]

    rows = frappe.get_all(
        "DMS Vehicle",
        filters=filters,
        fields=selected_fields,
        order_by="company_id asc, model asc, variant asc, name asc",
        limit_page_length=500,
    )

    companies = frappe.get_all(
        "DMS Company",
        fields=["name", "company_name"],
        order_by="company_name asc",
        limit_page_length=50,
    )
    company_map = {
        str(row["name"]): str(row["company_name"])
        for row in companies
    }

    normalized_rows: list[dict[str, Any]] = []
    company_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for raw in rows:
        row = dict(raw)
        company_name = company_map.get(
            str(row.get("company_id") or ""),
            str(row.get("company_id") or "Unknown"),
        )
        status = str(row.get("stock_status") or "Unknown")

        row["company_name"] = company_name
        normalized_rows.append(row)
        company_counts[company_name] += 1
        status_counts[status] += 1

    if admin:
        scope_label = "All Companies"
    else:
        scope_label = company_map.get(
            str(company_id),
            str(company_id or "Current Company"),
        )

    return {
        "rows": normalized_rows,
        "total": len(normalized_rows),
        "scope_label": scope_label,
        "is_group_admin": admin,
        "company_id": company_id,
        "company_counts": dict(sorted(company_counts.items())),
        "status_counts": {
            status: int(status_counts.get(status, 0))
            for status in ["In Stock", "Booked", "Transit", "Sold"]
        },
        "data_source": "DMS Vehicle",
        "session_user": user,
    }


@frappe.whitelist()
def list_inventory():
    return success(data=_inventory_payload())
