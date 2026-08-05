from __future__ import annotations

from collections import defaultdict
from typing import Any

from dms.agent.registry import register_tool
from dms.agent.semantics import (
    METRIC_CATALOG,
    RESOURCE_SEMANTICS,
    clean_company,
    clean_status,
    first_date_value,
    parse_date,
    semantic_spec,
)
from dms.agent.types import ToolContext


RESOURCE_ENUM = sorted(RESOURCE_SEMANTICS)
NULLABLE_STRING = {
    "anyOf": [
        {"type": "string"},
        {"type": "null"},
    ]
}


def _base():
    from dms.api import ai_agent
    return ai_agent


def _catalog_entry(resource: str) -> dict[str, Any]:
    meta = _base()._data_agent_catalog().get(resource)
    if not meta:
        raise ValueError(f"DMS resource is not available: {resource}")
    return meta


def _fetch_authorised_rows(
    resource: str,
    *,
    query: str,
    companies: list[str],
    statuses: list[str],
    is_chart: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = _base()
    meta = _catalog_entry(resource)
    intent = {
        "mode": "agentic_tool",
        "resources": [resource],
        "companies": companies,
        "statuses": statuses,
        "is_chart": is_chart,
    }
    rows = base._ultra_fetch(
        resource,
        meta["doctype"],
        query,
        intent,
    )
    return [dict(row) for row in rows], meta


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    resource: str,
    companies: list[str],
    statuses: list[str],
    date_from: str | None,
    date_to: str | None,
    search_text: str = "",
) -> list[dict[str, Any]]:
    wanted_companies = {
        str(value).strip().lower()
        for value in companies
        if str(value).strip()
    }
    wanted_statuses = {
        str(value).strip().lower()
        for value in statuses
        if str(value).strip()
    }
    start = parse_date(date_from)
    end = parse_date(date_to)
    terms = [
        token for token in str(search_text or "").lower().split()
        if token
    ]
    filtered: list[dict[str, Any]] = []

    for row in rows:
        company = clean_company(row).lower()
        if wanted_companies and company not in wanted_companies:
            if not any(
                wanted in company or company in wanted
                for wanted in wanted_companies
            ):
                continue

        status = clean_status(row, resource).lower()
        if wanted_statuses and status not in wanted_statuses:
            if not any(
                wanted in status or status in wanted
                for wanted in wanted_statuses
            ):
                continue

        _date_field, date_value = first_date_value(row, resource)
        row_date = parse_date(date_value)
        if start and (not row_date or row_date < start):
            continue
        if end and (not row_date or row_date > end):
            continue

        if terms:
            haystack = " ".join(
                str(value or "").lower()
                for value in row.values()
            )
            if not all(term in haystack for term in terms):
                continue
        filtered.append(row)

    return filtered


def _numeric(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _group_key(
    row: dict[str, Any],
    *,
    resource: str,
    group_by: str,
) -> tuple[str, dict[str, Any]]:
    if group_by == "none":
        return "All", {"group": "All"}
    if group_by == "company":
        company = clean_company(row)
        return company, {"company": company}
    if group_by == "status":
        status = clean_status(row, resource)
        return status, {"status": status}
    if group_by == "model":
        model = str(
            row.get("model")
            or row.get("vehicle_name")
            or row.get("variant")
            or "Unknown"
        ).strip()
        return model, {"model": model}

    date_field, date_value = first_date_value(row, resource)
    row_date = parse_date(date_value)
    month = row_date.strftime("%Y-%m") if row_date else "Unknown"
    if group_by == "month":
        return month, {"month": month, "date_field": date_field}
    if group_by == "company_month":
        company = clean_company(row)
        return (
            f"{company}|{month}",
            {
                "company": company,
                "month": month,
                "date_field": date_field,
            },
        )
    raise ValueError(f"Unsupported grouping: {group_by}")


@register_tool(
    name="list_dms_capabilities",
    description=(
        "List read-only DMS resources, business metrics and analytical "
        "operations. Use for broad requests or capability discovery."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
)
def list_dms_capabilities(
    context: ToolContext,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    del arguments
    return {
        "ok": True,
        "scope": context.public_scope(),
        "resources": {
            resource: {
                "description": spec["description"],
                "dimensions": spec["dimensions"],
                "numeric_fields": spec["numeric_fields"],
            }
            for resource, spec in RESOURCE_SEMANTICS.items()
        },
        "metrics": METRIC_CATALOG,
        "operations": [
            "describe resource",
            "query authorised records",
            "aggregate count/sum/average/min/max",
            "group by company/month/company+month/status/model",
        ],
    }


@register_tool(
    name="describe_dms_resource",
    description=(
        "Describe a DMS resource, its business meaning, dimensions, "
        "date fields and numeric measures before querying it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "resource": {
                "type": "string",
                "enum": RESOURCE_ENUM,
            },
        },
        "required": ["resource"],
        "additionalProperties": False,
    },
)
def describe_dms_resource(
    context: ToolContext,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    resource = arguments["resource"]
    meta = _catalog_entry(resource)
    return {
        "ok": True,
        "scope": context.public_scope(),
        "resource": resource,
        "title": meta["title"],
        "doctype": meta["doctype"],
        "semantic_definition": semantic_spec(resource),
    }


@register_tool(
    name="query_dms_records",
    description=(
        "Search and return authorised DMS records for exact lookups, "
        "lists and detail questions. Tenant scope is enforced first."
    ),
    parameters={
        "type": "object",
        "properties": {
            "resource": {
                "type": "string",
                "enum": RESOURCE_ENUM,
            },
            "search_text": {"type": "string"},
            "companies": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
            "statuses": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
            "date_from": NULLABLE_STRING,
            "date_to": NULLABLE_STRING,
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 30,
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": [
            "resource", "search_text", "companies", "statuses",
            "date_from", "date_to", "fields", "limit",
        ],
        "additionalProperties": False,
    },
)
def query_dms_records(
    context: ToolContext,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    resource = arguments["resource"]
    spec = semantic_spec(resource)
    rows, meta = _fetch_authorised_rows(
        resource,
        query=arguments["search_text"],
        companies=arguments["companies"],
        statuses=arguments["statuses"],
        is_chart=False,
    )
    filtered = _filter_rows(
        rows,
        resource=resource,
        companies=arguments["companies"],
        statuses=arguments["statuses"],
        date_from=arguments["date_from"],
        date_to=arguments["date_to"],
        search_text=arguments["search_text"],
    )

    allowed_fields = set(
        _base()._ultra_fields(resource, meta["doctype"])
    )
    requested = [
        field for field in arguments["fields"]
        if field in allowed_fields
    ]
    fields = requested or [
        field for field in spec["default_fields"]
        if field in allowed_fields
    ]
    if "name" in allowed_fields and "name" not in fields:
        fields.insert(0, "name")

    limit = min(int(arguments["limit"]), 100)
    result_rows = [
        {field: row.get(field) for field in fields}
        for row in filtered[:limit]
    ]
    return {
        "ok": True,
        "scope": context.public_scope(),
        "resource": resource,
        "doctype": meta["doctype"],
        "filters": {
            "search_text": arguments["search_text"],
            "companies": arguments["companies"],
            "statuses": arguments["statuses"],
            "date_from": arguments["date_from"],
            "date_to": arguments["date_to"],
        },
        "authorised_rows_scanned": len(rows),
        "matching_rows": len(filtered),
        "returned_rows": len(result_rows),
        "fields": fields,
        "rows": result_rows,
        "data_source": "frappe_authorised_records",
    }


@register_tool(
    name="aggregate_dms_records",
    description=(
        "Perform exact read-only aggregation over authorised DMS records. "
        "Use count for record totals; sum/average/min/max require an allowed "
        "numeric value_field. Supports company, month, company_month, "
        "status and model breakdowns."
    ),
    parameters={
        "type": "object",
        "properties": {
            "resource": {
                "type": "string",
                "enum": RESOURCE_ENUM,
            },
            "companies": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
            "statuses": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
            "date_from": NULLABLE_STRING,
            "date_to": NULLABLE_STRING,
            "group_by": {
                "type": "string",
                "enum": [
                    "none", "company", "month",
                    "company_month", "status", "model",
                ],
            },
            "aggregation": {
                "type": "string",
                "enum": ["count", "sum", "average", "min", "max"],
            },
            "value_field": NULLABLE_STRING,
            "limit_groups": {
                "type": "integer",
                "minimum": 1,
                "maximum": 120,
            },
        },
        "required": [
            "resource", "companies", "statuses", "date_from", "date_to",
            "group_by", "aggregation", "value_field", "limit_groups",
        ],
        "additionalProperties": False,
    },
)
def aggregate_dms_records(
    context: ToolContext,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    resource = arguments["resource"]
    aggregation = arguments["aggregation"]
    spec = semantic_spec(resource)

    value_field = arguments["value_field"]
    if aggregation == "count":
        value_field = None
    else:
        value_field = value_field or spec.get("default_value_field")
        if value_field not in spec["numeric_fields"]:
            raise ValueError(
                f"{resource}.{value_field} is not an allowed numeric metric"
            )

    rows, meta = _fetch_authorised_rows(
        resource,
        query=(
            f"aggregate {aggregation} {resource} "
            f"grouped by {arguments['group_by']}"
        ),
        companies=arguments["companies"],
        statuses=arguments["statuses"],
        is_chart=True,
    )
    filtered = _filter_rows(
        rows,
        resource=resource,
        companies=arguments["companies"],
        statuses=arguments["statuses"],
        date_from=arguments["date_from"],
        date_to=arguments["date_to"],
    )

    buckets: dict[str, dict[str, Any]] = {}
    values: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)

    for row in filtered:
        key, dimensions = _group_key(
            row,
            resource=resource,
            group_by=arguments["group_by"],
        )
        buckets[key] = dimensions
        counts[key] += 1
        if value_field:
            number = _numeric(row.get(value_field))
            if number is not None:
                values[key].append(number)

    output_rows: list[dict[str, Any]] = []
    for key in sorted(buckets):
        group_values = values.get(key, [])
        if aggregation == "count":
            value: float | int | None = counts[key]
        elif aggregation == "sum":
            value = round(sum(group_values), 2)
        elif aggregation == "average":
            value = (
                round(sum(group_values) / len(group_values), 2)
                if group_values else None
            )
        elif aggregation == "min":
            value = min(group_values) if group_values else None
        elif aggregation == "max":
            value = max(group_values) if group_values else None
        else:
            raise ValueError(f"Unsupported aggregation: {aggregation}")

        output_rows.append(
            {
                **buckets[key],
                "value": value,
                "record_count": counts[key],
            }
        )

    output_rows = output_rows[: min(int(arguments["limit_groups"]), 120)]
    numeric_values = [
        float(row["value"])
        for row in output_rows
        if isinstance(row.get("value"), (int, float))
    ]
    return {
        "ok": True,
        "scope": context.public_scope(),
        "resource": resource,
        "doctype": meta["doctype"],
        "aggregation": aggregation,
        "value_field": value_field,
        "group_by": arguments["group_by"],
        "filters": {
            "companies": arguments["companies"],
            "statuses": arguments["statuses"],
            "date_from": arguments["date_from"],
            "date_to": arguments["date_to"],
        },
        "authorised_rows_scanned": len(rows),
        "matching_rows": len(filtered),
        "group_count": len(output_rows),
        "rows": output_rows,
        "total_value": (
            round(sum(numeric_values), 2)
            if numeric_values else 0
        ),
        "data_source": "frappe_authorised_records",
    }
