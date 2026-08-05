from __future__ import annotations

from datetime import date, datetime
from typing import Any


RESOURCE_SEMANTICS: dict[str, dict[str, Any]] = {
    "customers": {
        "description": "Customer master records and contact details.",
        "date_fields": ["creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["status", "customer_type"],
        "dimensions": ["company_name", "customer_type", "status", "creation"],
        "numeric_fields": [],
        "default_fields": [
            "name", "customer_name", "mobile_no", "email",
            "company_name", "customer_type", "status", "creation",
        ],
    },
    "leads": {
        "description": "Sales leads, source, status and vehicle interest.",
        "date_fields": ["creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["status"],
        "dimensions": [
            "company_name", "source", "status",
            "vehicle_interest", "creation",
        ],
        "numeric_fields": [],
        "default_fields": [
            "name", "lead_name", "mobile_no", "email", "company_name",
            "source", "status", "vehicle_interest", "creation",
        ],
    },
    "sales": {
        "description": (
            "Vehicle sales. Count records for units sold and sum "
            "final_price for sales revenue."
        ),
        "date_fields": ["creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["status"],
        "dimensions": [
            "company_name", "model", "variant", "status", "creation",
        ],
        "numeric_fields": ["final_price"],
        "default_value_field": "final_price",
        "default_fields": [
            "name", "customer_name", "company_name", "model", "variant",
            "final_price", "status", "invoice_no", "creation",
        ],
    },
    "invoices": {
        "description": (
            "Invoices, payment state and monetary value. Sum total_amount "
            "for invoiced value."
        ),
        "date_fields": ["creation", "due_date"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["payment_status", "status"],
        "dimensions": [
            "company_name", "invoice_type", "payment_status",
            "status", "creation", "due_date",
        ],
        "numeric_fields": ["total_amount"],
        "default_value_field": "total_amount",
        "default_fields": [
            "name", "invoice_no", "customer_name", "company_name",
            "invoice_type", "total_amount", "payment_status",
            "status", "due_date", "creation",
        ],
    },
    "bookings": {
        "description": "Vehicle bookings, delivery status and booking value.",
        "date_fields": ["booking_date", "creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["status"],
        "dimensions": [
            "company_name", "model", "variant", "status",
            "booking_date", "expected_delivery",
        ],
        "numeric_fields": ["booking_amount"],
        "default_value_field": "booking_amount",
        "default_fields": [
            "name", "customer_name", "company_name", "model", "variant",
            "booking_amount", "booking_date", "expected_delivery", "status",
        ],
    },
    "test_drives": {
        "description": "Scheduled test drives and their completion status.",
        "date_fields": ["scheduled_date", "creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["status"],
        "dimensions": ["company_name", "model", "status", "scheduled_date"],
        "numeric_fields": [],
        "default_fields": [
            "name", "contact_name", "customer_name", "company_name",
            "model", "scheduled_date", "scheduled_time", "status",
        ],
    },
    "service_jobs": {
        "description": (
            "Service jobs, operational status and service billing value."
        ),
        "date_fields": ["creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["status"],
        "dimensions": [
            "company_name", "model", "service_type", "status", "creation",
        ],
        "numeric_fields": ["total_amount"],
        "default_value_field": "total_amount",
        "default_fields": [
            "name", "customer_name", "company_name", "vehicle_reg_no",
            "model", "service_type", "total_amount", "status", "creation",
        ],
    },
    "vehicles": {
        "description": "Vehicle inventory and stock availability.",
        "date_fields": ["creation"],
        "company_fields": ["company_name", "company_id"],
        "status_fields": ["stock_status", "status"],
        "dimensions": [
            "company_name", "model", "variant", "color",
            "stock_status", "status", "creation",
        ],
        "numeric_fields": [],
        "default_fields": [
            "name", "vehicle_name", "company_name", "model", "variant",
            "color", "stock_status", "status", "creation",
        ],
    },
}


METRIC_CATALOG: dict[str, dict[str, Any]] = {
    "customer_count": {
        "resource": "customers",
        "aggregation": "count",
        "description": "Number of authorised customer records.",
    },
    "lead_count": {
        "resource": "leads",
        "aggregation": "count",
        "description": "Number of authorised lead records.",
    },
    "vehicle_sales_count": {
        "resource": "sales",
        "aggregation": "count",
        "description": "Number of authorised vehicle sale records.",
    },
    "invoice_count": {
        "resource": "invoices",
        "aggregation": "count",
        "description": "Number of authorised invoice records.",
    },
    "booking_count": {
        "resource": "bookings",
        "aggregation": "count",
        "description": "Number of authorised booking records.",
    },
    "test_drive_count": {
        "resource": "test_drives",
        "aggregation": "count",
        "description": "Number of authorised test-drive records.",
    },
    "service_job_count": {
        "resource": "service_jobs",
        "aggregation": "count",
        "description": "Number of authorised service-job records.",
    },
    "inventory_vehicle_count": {
        "resource": "vehicles",
        "aggregation": "count",
        "description": "Number of authorised vehicle inventory records.",
    },
    "sales_revenue": {
        "resource": "sales",
        "aggregation": "sum",
        "value_field": "final_price",
        "description": "Exact sum of final_price across authorised sales.",
    },
    "average_sale_value": {
        "resource": "sales",
        "aggregation": "average",
        "value_field": "final_price",
        "description": "Exact average final_price across authorised sales.",
    },
    "minimum_sale_value": {
        "resource": "sales",
        "aggregation": "min",
        "value_field": "final_price",
        "description": "Minimum final_price across authorised sales.",
    },
    "maximum_sale_value": {
        "resource": "sales",
        "aggregation": "max",
        "value_field": "final_price",
        "description": "Maximum final_price across authorised sales.",
    },
    "invoice_value": {
        "resource": "invoices",
        "aggregation": "sum",
        "value_field": "total_amount",
        "description": "Exact sum of authorised invoice total_amount.",
    },
    "average_invoice_value": {
        "resource": "invoices",
        "aggregation": "average",
        "value_field": "total_amount",
        "description": "Exact average authorised invoice total_amount.",
    },
    "minimum_invoice_value": {
        "resource": "invoices",
        "aggregation": "min",
        "value_field": "total_amount",
        "description": "Minimum authorised invoice total_amount.",
    },
    "maximum_invoice_value": {
        "resource": "invoices",
        "aggregation": "max",
        "value_field": "total_amount",
        "description": "Maximum authorised invoice total_amount.",
    },
    "booking_value": {
        "resource": "bookings",
        "aggregation": "sum",
        "value_field": "booking_amount",
        "description": "Exact sum of authorised booking_amount.",
    },
    "average_booking_value": {
        "resource": "bookings",
        "aggregation": "average",
        "value_field": "booking_amount",
        "description": "Exact average authorised booking_amount.",
    },
    "minimum_booking_value": {
        "resource": "bookings",
        "aggregation": "min",
        "value_field": "booking_amount",
        "description": "Minimum authorised booking_amount.",
    },
    "maximum_booking_value": {
        "resource": "bookings",
        "aggregation": "max",
        "value_field": "booking_amount",
        "description": "Maximum authorised booking_amount.",
    },
    "service_revenue": {
        "resource": "service_jobs",
        "aggregation": "sum",
        "value_field": "total_amount",
        "description": "Exact sum of authorised service-job total_amount.",
    },
    "average_service_value": {
        "resource": "service_jobs",
        "aggregation": "average",
        "value_field": "total_amount",
        "description": "Exact average authorised service-job total_amount.",
    },
    "minimum_service_value": {
        "resource": "service_jobs",
        "aggregation": "min",
        "value_field": "total_amount",
        "description": "Minimum authorised service-job total_amount.",
    },
    "maximum_service_value": {
        "resource": "service_jobs",
        "aggregation": "max",
        "value_field": "total_amount",
        "description": "Maximum authorised service-job total_amount.",
    },
}


def semantic_spec(resource: str) -> dict[str, Any]:
    if resource not in RESOURCE_SEMANTICS:
        raise ValueError(f"Unsupported DMS resource: {resource}")
    return RESOURCE_SEMANTICS[resource]


def clean_company(row: dict[str, Any]) -> str:
    return str(
        row.get("company_name")
        or row.get("company_id")
        or "Unknown"
    ).strip()


def clean_status(row: dict[str, Any], resource: str) -> str:
    spec = semantic_spec(resource)
    for field in spec["status_fields"]:
        value = row.get(field)
        if value not in (None, ""):
            return str(value).strip()
    return "Unknown"


def first_date_value(
    row: dict[str, Any],
    resource: str,
) -> tuple[str, Any]:
    spec = semantic_spec(resource)
    for field in spec["date_fields"]:
        value = row.get(field)
        if value not in (None, ""):
            return field, value
    return spec["date_fields"][0], None


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for candidate in (text, text[:19], text[:10]):
        try:
            return datetime.fromisoformat(
                candidate.replace("Z", "+00:00")
            ).date()
        except Exception:
            pass
    return None
