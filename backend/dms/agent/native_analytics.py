from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re
import uuid
from typing import Any, Iterable

import frappe
from frappe.utils import getdate

from dms.agent.semantics import RESOURCE_SEMANTICS, semantic_spec
from dms.agent.types import ToolContext


NUMERIC_FIELD_TYPES = {
    "Currency",
    "Float",
    "Int",
    "Long Int",
    "Percent",
    "Decimal",
}
DATE_FIELD_TYPES = {"Date", "Datetime"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")
GENERIC_COMPANY_TERMS = {
    "all",
    "all companies",
    "all tenants",
    "all brands",
    "group",
    "group wide",
    "group-wide",
}


@dataclass(frozen=True)
class RuntimeResource:
    resource: str
    doctype: str
    table: str
    company_fields: tuple[str, ...]
    status_field: str | None
    date_field: str | None
    date_fieldtype: str | None
    model_fields: tuple[str, ...]
    numeric_fields: tuple[str, ...]


def _base():
    from dms.api import ai_agent

    return ai_agent


def _normalise_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _quote_identifier(value: str) -> str:
    if not value or not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Unsafe database field identifier: {value!r}")
    db_type = str(getattr(frappe.db, "db_type", "") or "").lower()
    quote = '"' if "postgres" in db_type else "`"
    return f"{quote}{value}{quote}"


def _quote_table(doctype: str) -> str:
    if not doctype or "`" in doctype or '"' in doctype:
        raise ValueError("Unsafe DocType name")
    db_type = str(getattr(frappe.db, "db_type", "") or "").lower()
    quote = '"' if "postgres" in db_type else "`"
    return f"{quote}tab{doctype}{quote}"


def _fieldtype(meta: Any, fieldname: str) -> str | None:
    if fieldname in {"creation", "modified"}:
        return "Datetime"
    if fieldname in {"docstatus", "idx"}:
        return "Int"
    field = meta.get_field(fieldname)
    return str(field.fieldtype) if field else None


def _existing_fields(meta: Any) -> set[str]:
    fields = {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
    }
    fields.update(
        str(field.fieldname)
        for field in (meta.fields or [])
        if getattr(field, "fieldname", None)
    )
    return fields


def resolve_runtime_resource(resource: str) -> RuntimeResource:
    spec = semantic_spec(resource)
    catalog = _base()._data_agent_catalog()
    entry = catalog.get(resource)
    if not entry:
        raise ValueError(f"DMS resource is not available: {resource}")

    doctype = str(entry.get("doctype") or "").strip()
    if not doctype:
        raise ValueError(f"DMS resource has no DocType: {resource}")

    meta = frappe.get_meta(doctype)
    existing = _existing_fields(meta)

    company_fields = tuple(
        field
        for field in spec.get("company_fields") or []
        if field in existing
    )
    status_field = next(
        (
            field
            for field in spec.get("status_fields") or []
            if field in existing
        ),
        None,
    )
    date_field = next(
        (
            field
            for field in spec.get("date_fields") or []
            if field in existing
            and _fieldtype(meta, field) in DATE_FIELD_TYPES
        ),
        None,
    )
    model_fields = tuple(
        field
        for field in ("model", "vehicle_name", "variant")
        if field in existing
    )
    numeric_fields = tuple(
        field
        for field in spec.get("numeric_fields") or []
        if field in existing
        and _fieldtype(meta, field) in NUMERIC_FIELD_TYPES
    )

    return RuntimeResource(
        resource=resource,
        doctype=doctype,
        table=_quote_table(doctype),
        company_fields=company_fields,
        status_field=status_field,
        date_field=date_field,
        date_fieldtype=(
            _fieldtype(meta, date_field)
            if date_field
            else None
        ),
        model_fields=model_fields,
        numeric_fields=numeric_fields,
    )


def _coalesce_text(fields: Iterable[str], fallback: str) -> str:
    expressions = [
        f"NULLIF(TRIM({_quote_identifier(field)}), '')"
        for field in fields
    ]
    if not expressions:
        raise ValueError("No compatible field is available for this grouping")
    return f"COALESCE({', '.join(expressions)}, '{fallback}')"


def _month_expression(field: str) -> str:
    identifier = _quote_identifier(field)
    db_type = str(getattr(frappe.db, "db_type", "") or "").lower()
    if "postgres" in db_type:
        return f"COALESCE(TO_CHAR({identifier}, 'YYYY-MM'), 'Unknown')"
    return f"COALESCE(DATE_FORMAT({identifier}, '%%Y-%%m'), 'Unknown')"


def _parse_date_bound(value: Any, label: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return getdate(value)
    except Exception as exc:
        raise ValueError(f"{label} must be a valid date") from exc


def _company_identity(value: Any) -> dict[str, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return {"raw": "", "id": None, "name": None}

    base = _base()
    alias_name = base._company_name_from_alias(raw)
    candidate_name = str(alias_name or raw).strip()

    company_id = None
    company_name = None
    try:
        by_id = frappe.db.get_value(
            "DMS Company",
            raw,
            ["name", "company_name"],
            as_dict=True,
        )
    except Exception:
        by_id = None
    if by_id:
        company_id = str(by_id.get("name") or raw)
        company_name = str(by_id.get("company_name") or company_id)

    if not company_id:
        try:
            by_name = frappe.db.get_value(
                "DMS Company",
                {"company_name": candidate_name},
                ["name", "company_name"],
                as_dict=True,
            )
        except Exception:
            by_name = None
        if by_name:
            company_id = str(by_name.get("name") or "")
            company_name = str(
                by_name.get("company_name")
                or candidate_name
            )

    if not company_name and candidate_name:
        company_name = candidate_name

    return {
        "raw": raw,
        "id": company_id,
        "name": company_name,
    }


def _identity_tokens(identity: dict[str, str | None]) -> set[str]:
    return {
        token
        for token in (
            _normalise_text(identity.get("raw")),
            _normalise_text(identity.get("id")),
            _normalise_text(identity.get("name")),
        )
        if token
    }


def _tenant_identity(context: ToolContext) -> dict[str, str | None]:
    identity = _company_identity(
        context.company_id or context.company_name or context.tenant_id
    )
    if context.company_id:
        identity["id"] = str(context.company_id)
    if context.company_name:
        identity["name"] = str(context.company_name)
    if not identity.get("id") and not identity.get("name"):
        raise PermissionError(
            "Tenant scope could not be resolved; database access is denied"
        )
    return identity


def _requested_identities(
    context: ToolContext,
    requested: list[str],
) -> list[dict[str, str | None]]:
    cleaned = [
        str(value).strip()
        for value in requested
        if str(value).strip()
    ]
    if context.is_admin:
        identities = []
        for value in cleaned:
            if _normalise_text(value) in GENERIC_COMPANY_TERMS:
                continue
            identities.append(_company_identity(value))
        return identities

    tenant = _tenant_identity(context)
    tenant_tokens = _identity_tokens(tenant)
    for value in cleaned:
        if _normalise_text(value) in GENERIC_COMPANY_TERMS:
            raise PermissionError(
                "Tenant users cannot request cross-company analytics"
            )
        requested_identity = _company_identity(value)
        if not (
            _identity_tokens(requested_identity)
            & tenant_tokens
        ):
            raise PermissionError(
                "Requested company is outside the authorised tenant scope"
            )
    return [tenant]


def _company_predicate(
    runtime: RuntimeResource,
    identities: list[dict[str, str | None]],
    params: dict[str, Any],
) -> str | None:
    if not identities:
        return None
    if not runtime.company_fields:
        raise PermissionError(
            f"{runtime.doctype} has no validated company scope field"
        )

    groups: list[str] = []
    for index, identity in enumerate(identities):
        terms: list[str] = []
        if (
            "company_id" in runtime.company_fields
            and identity.get("id")
        ):
            key = f"company_id_{index}"
            params[key] = identity["id"]
            terms.append(
                f"{_quote_identifier('company_id')} = %({key})s"
            )
        elif (
            "company_name" in runtime.company_fields
            and identity.get("name")
        ):
            key = f"company_name_{index}"
            params[key] = identity["name"]
            terms.append(
                f"{_quote_identifier('company_name')} = %({key})s"
            )

        raw = identity.get("raw")
        if raw and not terms:
            for field in runtime.company_fields:
                key = f"company_raw_{index}_{field}"
                params[key] = raw
                terms.append(
                    f"{_quote_identifier(field)} = %({key})s"
                )

        if terms:
            groups.append(f"({' OR '.join(terms)})")

    if not groups:
        raise PermissionError(
            "No validated company predicate could be constructed"
        )
    return f"({' OR '.join(groups)})"


def _status_predicate(
    runtime: RuntimeResource,
    statuses: list[str],
    params: dict[str, Any],
) -> str | None:
    cleaned = [
        str(value).strip()
        for value in statuses
        if str(value).strip()
    ]
    if not cleaned:
        return None
    if not runtime.status_field:
        raise ValueError(
            f"{runtime.resource} has no validated status field"
        )
    placeholders = []
    for index, value in enumerate(cleaned):
        key = f"status_{index}"
        params[key] = value
        placeholders.append(f"%({key})s")
    return (
        f"{_quote_identifier(runtime.status_field)} "
        f"IN ({', '.join(placeholders)})"
    )


def _date_predicates(
    runtime: RuntimeResource,
    date_from: Any,
    date_to: Any,
    params: dict[str, Any],
) -> list[str]:
    start = _parse_date_bound(date_from, "date_from")
    end = _parse_date_bound(date_to, "date_to")
    if start and end and start > end:
        raise ValueError("date_from cannot be later than date_to")
    if not start and not end:
        return []
    if not runtime.date_field:
        raise ValueError(
            f"{runtime.resource} has no validated business date field"
        )

    field = _quote_identifier(runtime.date_field)
    predicates: list[str] = []
    if runtime.date_fieldtype == "Date":
        if start:
            params["date_from"] = start.isoformat()
            predicates.append(f"{field} >= %(date_from)s")
        if end:
            params["date_to"] = end.isoformat()
            predicates.append(f"{field} <= %(date_to)s")
        return predicates

    if start:
        params["date_from"] = datetime.combine(start, time.min)
        predicates.append(f"{field} >= %(date_from)s")
    if end:
        params["date_to_exclusive"] = datetime.combine(
            end + timedelta(days=1),
            time.min,
        )
        predicates.append(
            f"{field} < %(date_to_exclusive)s"
        )
    return predicates


def build_trusted_predicates(
    runtime: RuntimeResource,
    context: ToolContext,
    arguments: dict[str, Any],
) -> tuple[str, dict[str, Any], list[dict[str, str | None]]]:
    params: dict[str, Any] = {}
    requested = list(arguments.get("companies") or [])
    identities = _requested_identities(context, requested)

    predicates: list[str] = []
    company_clause = _company_predicate(
        runtime,
        identities,
        params,
    )
    if company_clause:
        predicates.append(company_clause)

    status_clause = _status_predicate(
        runtime,
        list(arguments.get("statuses") or []),
        params,
    )
    if status_clause:
        predicates.append(status_clause)

    predicates.extend(
        _date_predicates(
            runtime,
            arguments.get("date_from"),
            arguments.get("date_to"),
            params,
        )
    )
    return (
        " AND ".join(predicates) if predicates else "1 = 1",
        params,
        identities,
    )


def _aggregation_expression(
    aggregation: str,
    value_field: str | None,
) -> str:
    if aggregation == "count":
        return "COUNT(*)"
    if not value_field:
        raise ValueError(
            f"{aggregation} requires a numeric value_field"
        )
    field = _quote_identifier(value_field)
    if aggregation == "sum":
        return f"COALESCE(SUM({field}), 0)"
    if aggregation == "average":
        return f"AVG({field})"
    if aggregation == "min":
        return f"MIN({field})"
    if aggregation == "max":
        return f"MAX({field})"
    raise ValueError(f"Unsupported aggregation: {aggregation}")


def _group_expressions(
    runtime: RuntimeResource,
    group_by: str,
) -> list[tuple[str, str]]:
    if group_by == "none":
        return []
    if group_by == "company":
        return [
            (
                "company",
                _coalesce_text(runtime.company_fields, "Unknown"),
            )
        ]
    if group_by == "month":
        if not runtime.date_field:
            raise ValueError(
                f"{runtime.resource} has no business date field"
            )
        return [
            (
                "month",
                _month_expression(runtime.date_field),
            )
        ]
    if group_by == "company_month":
        if not runtime.date_field:
            raise ValueError(
                f"{runtime.resource} has no business date field"
            )
        return [
            (
                "company",
                _coalesce_text(runtime.company_fields, "Unknown"),
            ),
            (
                "month",
                _month_expression(runtime.date_field),
            ),
        ]
    if group_by == "status":
        if not runtime.status_field:
            raise ValueError(
                f"{runtime.resource} has no status field"
            )
        return [
            (
                "status",
                _coalesce_text(
                    [runtime.status_field],
                    "Unknown",
                ),
            )
        ]
    if group_by == "model":
        if not runtime.model_fields:
            raise ValueError(
                f"{runtime.resource} has no model dimension"
            )
        return [
            (
                "model",
                _coalesce_text(runtime.model_fields, "Unknown"),
            )
        ]
    raise ValueError(f"Unsupported grouping: {group_by}")


def _normalise_number(
    value: Any,
    *,
    aggregation: str,
) -> int | float | None:
    if value is None:
        return None
    if aggregation == "count":
        return int(value)
    if isinstance(value, Decimal):
        value = float(value)
    try:
        return round(float(value), 2)
    except Exception as exc:
        raise ValueError(
            f"Database returned a non-numeric aggregate: {value!r}"
        ) from exc


def _sql_rows(
    query: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = frappe.db.sql(query, params, as_dict=True)
    return [dict(row) for row in (rows or [])]


def execute_native_aggregate(
    context: ToolContext,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    resource = str(arguments["resource"])
    aggregation = str(arguments["aggregation"])
    group_by = str(arguments["group_by"])
    runtime = resolve_runtime_resource(resource)
    spec = semantic_spec(resource)

    value_field = arguments.get("value_field")
    if aggregation == "count":
        value_field = None
    else:
        value_field = (
            str(value_field).strip()
            if value_field
            else spec.get("default_value_field")
        )
        if value_field not in runtime.numeric_fields:
            raise ValueError(
                f"{resource}.{value_field} is not an available "
                "validated numeric metric"
            )

    where_sql, params, identities = build_trusted_predicates(
        runtime,
        context,
        arguments,
    )
    aggregate_sql = _aggregation_expression(
        aggregation,
        value_field,
    )
    group_items = _group_expressions(runtime, group_by)

    overall_query = (
        f"SELECT COUNT(*) AS matching_rows, "
        f"{aggregate_sql} AS overall_value "
        f"FROM {runtime.table} WHERE {where_sql}"
    )
    overall_rows = _sql_rows(overall_query, params)
    overall_row = overall_rows[0] if overall_rows else {}
    matching_rows = int(overall_row.get("matching_rows") or 0)
    overall_value = _normalise_number(
        overall_row.get("overall_value"),
        aggregation=aggregation,
    )
    if aggregation in {"count", "sum"} and overall_value is None:
        overall_value = 0 if aggregation == "count" else 0.0

    if matching_rows == 0:
        return {
            "ok": True,
            "scope": context.public_scope(),
            "resource": resource,
            "doctype": runtime.doctype,
            "aggregation": aggregation,
            "value_field": value_field,
            "group_by": group_by,
            "business_date_field": runtime.date_field,
            "status_field": runtime.status_field,
            "filters": {
                "companies": list(arguments.get("companies") or []),
                "statuses": list(arguments.get("statuses") or []),
                "date_from": arguments.get("date_from"),
                "date_to": arguments.get("date_to"),
            },
            "effective_companies": [
                identity.get("name") or identity.get("id")
                for identity in identities
            ],
            "matching_rows": 0,
            "overall_value": overall_value,
            "total_value": overall_value,
            "returned_groups": 0,
            "total_groups": 0,
            "group_count": 0,
            "truncated_groups": False,
            "rows": [],
            "data_source": "frappe_database_native_aggregation",
        }

    if not group_items:
        total_groups = 1
        output_rows = [
            {
                "group": "All",
                "value": overall_value,
                "record_count": matching_rows,
            }
        ]
    else:
        select_dimensions = ", ".join(
            f"{expression} AS {_quote_identifier(alias)}"
            for alias, expression in group_items
        )
        group_sql = ", ".join(
            expression for _alias, expression in group_items
        )
        count_groups_query = (
            "SELECT COUNT(*) AS total_groups FROM ("
            f"SELECT 1 FROM {runtime.table} "
            f"WHERE {where_sql} GROUP BY {group_sql}"
            ") native_groups"
        )
        count_rows = _sql_rows(count_groups_query, params)
        total_groups = int(
            (count_rows[0] if count_rows else {}).get(
                "total_groups"
            )
            or 0
        )

        limit_groups = min(
            max(int(arguments.get("limit_groups") or 1), 1),
            120,
        )
        grouped_query = (
            f"SELECT {select_dimensions}, "
            f"{aggregate_sql} AS value, "
            "COUNT(*) AS record_count "
            f"FROM {runtime.table} "
            f"WHERE {where_sql} "
            f"GROUP BY {group_sql} "
            f"ORDER BY {group_sql} "
            f"LIMIT {limit_groups}"
        )
        raw_rows = _sql_rows(grouped_query, params)
        output_rows = []
        for raw in raw_rows:
            row = {
                alias: raw.get(alias)
                for alias, _expression in group_items
            }
            row["value"] = _normalise_number(
                raw.get("value"),
                aggregation=aggregation,
            )
            row["record_count"] = int(
                raw.get("record_count") or 0
            )
            output_rows.append(row)

    returned_groups = len(output_rows)
    return {
        "ok": True,
        "scope": context.public_scope(),
        "resource": resource,
        "doctype": runtime.doctype,
        "aggregation": aggregation,
        "value_field": value_field,
        "group_by": group_by,
        "business_date_field": runtime.date_field,
        "status_field": runtime.status_field,
        "filters": {
            "companies": list(arguments.get("companies") or []),
            "statuses": list(arguments.get("statuses") or []),
            "date_from": arguments.get("date_from"),
            "date_to": arguments.get("date_to"),
        },
        "effective_companies": [
            identity.get("name") or identity.get("id")
            for identity in identities
        ],
        "matching_rows": matching_rows,
        "overall_value": overall_value,
        "total_value": overall_value,
        "returned_groups": returned_groups,
        "total_groups": total_groups,
        "group_count": returned_groups,
        "truncated_groups": returned_groups < total_groups,
        "rows": output_rows,
        "data_source": "frappe_database_native_aggregation",
    }


def _admin_context() -> ToolContext:
    return ToolContext(
        request_id=f"step3-probe-{uuid.uuid4()}",
        user="Administrator",
        role="group_admin",
        tenant_id=None,
        is_admin=True,
        company_id=None,
        company_name=None,
    )


def _arguments(
    resource: str,
    *,
    aggregation: str = "count",
    value_field: str | None = None,
    group_by: str = "none",
    companies: list[str] | None = None,
    statuses: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit_groups: int = 120,
) -> dict[str, Any]:
    return {
        "resource": resource,
        "companies": companies or [],
        "statuses": statuses or [],
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "aggregation": aggregation,
        "value_field": value_field,
        "limit_groups": limit_groups,
    }


def runtime_probe() -> dict[str, Any]:
    resources = {}
    for resource in sorted(RESOURCE_SEMANTICS):
        runtime = resolve_runtime_resource(resource)
        resources[resource] = {
            "doctype": runtime.doctype,
            "company_fields": list(runtime.company_fields),
            "status_field": runtime.status_field,
            "date_field": runtime.date_field,
            "date_fieldtype": runtime.date_fieldtype,
            "model_fields": list(runtime.model_fields),
            "numeric_fields": list(runtime.numeric_fields),
        }
    return {
        "status": "ok",
        "database_type": str(
            getattr(frappe.db, "db_type", "") or "unknown"
        ),
        "resource_count": len(resources),
        "resources": resources,
    }


def _close_numbers(
    left: int | float | None,
    right: int | float | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return abs(float(left) - float(right)) <= 0.01


def validation_probe() -> dict[str, Any]:
    context = _admin_context()
    resource_counts = {}
    for resource in sorted(RESOURCE_SEMANTICS):
        result = execute_native_aggregate(
            context,
            _arguments(resource),
        )
        runtime = resolve_runtime_resource(resource)
        reference_rows = _sql_rows(
            f"SELECT COUNT(*) AS value FROM {runtime.table}",
            {},
        )
        reference = int(
            (reference_rows[0] if reference_rows else {}).get(
                "value"
            )
            or 0
        )
        if result["matching_rows"] != reference:
            raise AssertionError(
                f"{resource} count mismatch: "
                f"{result['matching_rows']} != {reference}"
            )
        if result["overall_value"] != reference:
            raise AssertionError(
                f"{resource} overall count mismatch"
            )
        resource_counts[resource] = reference

    sales = resolve_runtime_resource("sales")
    if "final_price" not in sales.numeric_fields:
        raise AssertionError(
            "sales.final_price is not available as a numeric field"
        )

    numeric_checks = {}
    for resource in sorted(RESOURCE_SEMANTICS):
        runtime = resolve_runtime_resource(resource)
        if not runtime.numeric_fields:
            continue
        resource_checks = {}
        for value_field in runtime.numeric_fields:
            field_checks = {}
            for aggregation in ("sum", "average", "min", "max"):
                result = execute_native_aggregate(
                    context,
                    _arguments(
                        resource,
                        aggregation=aggregation,
                        value_field=value_field,
                    ),
                )
                expression = _aggregation_expression(
                    aggregation,
                    value_field,
                )
                reference_rows = _sql_rows(
                    f"SELECT {expression} AS value "
                    f"FROM {runtime.table}",
                    {},
                )
                reference = _normalise_number(
                    (
                        reference_rows[0]
                        if reference_rows
                        else {}
                    ).get("value"),
                    aggregation=aggregation,
                )
                if aggregation == "sum" and reference is None:
                    reference = 0.0
                if not _close_numbers(
                    result["overall_value"],
                    reference,
                ):
                    raise AssertionError(
                        f"{resource}.{value_field} "
                        f"{aggregation} mismatch: "
                        f"{result['overall_value']} != {reference}"
                    )
                field_checks[aggregation] = result["overall_value"]
            resource_checks[value_field] = field_checks
        numeric_checks[resource] = resource_checks

    grouping_checks = {}
    for group_by in (
        "company",
        "month",
        "company_month",
        "status",
        "model",
    ):
        result = execute_native_aggregate(
            context,
            _arguments(
                "sales",
                group_by=group_by,
                limit_groups=120,
            ),
        )
        if not result["truncated_groups"]:
            grouped_count = sum(
                int(row.get("record_count") or 0)
                for row in result["rows"]
            )
            if grouped_count != result["matching_rows"]:
                raise AssertionError(
                    f"sales {group_by} grouped count mismatch"
                )
        if result["returned_groups"] > 120:
            raise AssertionError("group payload limit was exceeded")
        grouping_checks[group_by] = {
            "total": result["total_groups"],
            "returned": result["returned_groups"],
            "truncated": result["truncated_groups"],
        }

    limited = execute_native_aggregate(
        context,
        _arguments(
            "sales",
            group_by="company_month",
            limit_groups=1,
        ),
    )
    if limited["returned_groups"] > 1:
        raise AssertionError("limit_groups=1 was not enforced")
    if limited["truncated_groups"] != (
        limited["total_groups"] > 1
    ):
        raise AssertionError("truncated_groups is incorrect")

    empty_status = f"__STEP3_NO_MATCH_{uuid.uuid4()}__"
    empty_count = execute_native_aggregate(
        context,
        _arguments(
            "sales",
            statuses=[empty_status],
        ),
    )
    empty_average = execute_native_aggregate(
        context,
        _arguments(
            "sales",
            aggregation="average",
            value_field="final_price",
            statuses=[empty_status],
        ),
    )
    if (
        empty_count["matching_rows"] != 0
        or empty_count["overall_value"] != 0
        or empty_count["rows"]
    ):
        raise AssertionError("empty count contract failed")
    if (
        empty_average["matching_rows"] != 0
        or empty_average["overall_value"] is not None
        or empty_average["rows"]
    ):
        raise AssertionError("empty average contract failed")

    companies = frappe.get_all(
        "DMS Company",
        fields=["name", "company_name"],
        order_by="name asc",
        limit_page_length=2,
    )
    tenant_security = {"companies_available": len(companies)}
    if companies:
        first = companies[0]
        tenant = ToolContext(
            request_id=f"step3-tenant-{uuid.uuid4()}",
            user="step3-probe",
            role="tenant_user",
            tenant_id=str(first.get("name") or ""),
            is_admin=False,
            company_id=str(first.get("name") or ""),
            company_name=str(
                first.get("company_name")
                or first.get("name")
                or ""
            ),
        )
        own = execute_native_aggregate(
            tenant,
            _arguments("sales"),
        )
        if own["matching_rows"] > resource_counts["sales"]:
            raise AssertionError("tenant result exceeds admin result")
        tenant_security["own_count"] = own["matching_rows"]

        if len(companies) > 1:
            other = companies[1]
            denied = False
            try:
                execute_native_aggregate(
                    tenant,
                    _arguments(
                        "sales",
                        companies=[
                            str(
                                other.get("company_name")
                                or other.get("name")
                            )
                        ],
                    ),
                )
            except PermissionError:
                denied = True
            if not denied:
                raise AssertionError(
                    "cross-tenant company request was not denied"
                )
            tenant_security["cross_tenant_denied"] = True

    date_identifier = _quote_identifier(
        sales.date_field or "creation"
    )
    latest = _sql_rows(
        f"SELECT {date_identifier} AS value "
        f"FROM {sales.table} "
        f"WHERE {date_identifier} IS NOT NULL "
        f"ORDER BY {date_identifier} DESC LIMIT 1",
        {},
    )
    same_day = None
    if latest:
        latest_value = latest[0].get("value")
        if latest_value:
            target = getdate(latest_value).isoformat()
            same_day_result = execute_native_aggregate(
                context,
                _arguments(
                    "sales",
                    date_from=target,
                    date_to=target,
                ),
            )
            if sales.date_fieldtype == "Date":
                reference_sql = (
                    f"SELECT COUNT(*) AS value FROM {sales.table} "
                    f"WHERE {date_identifier} >= %(start)s "
                    f"AND {date_identifier} <= %(end)s"
                )
                reference_params = {
                    "start": target,
                    "end": target,
                }
            else:
                reference_sql = (
                    f"SELECT COUNT(*) AS value FROM {sales.table} "
                    f"WHERE {date_identifier} >= %(start)s "
                    f"AND {date_identifier} < %(end)s"
                )
                reference_params = {
                    "start": datetime.combine(
                        getdate(target),
                        time.min,
                    ),
                    "end": datetime.combine(
                        getdate(target) + timedelta(days=1),
                        time.min,
                    ),
                }
            reference_rows = _sql_rows(
                reference_sql,
                reference_params,
            )
            reference = int(
                (reference_rows[0] if reference_rows else {}).get(
                    "value"
                )
                or 0
            )
            if same_day_result["matching_rows"] != reference:
                raise AssertionError(
                    "inclusive same-day datetime filter failed"
                )
            same_day = {
                "date": target,
                "count": reference,
            }

    return {
        "status": "pass",
        "resource_counts": resource_counts,
        "numeric_checks": numeric_checks,
        "grouping_checks": grouping_checks,
        "limit_check": {
            "total": limited["total_groups"],
            "returned": limited["returned_groups"],
            "truncated": limited["truncated_groups"],
        },
        "empty_contract": True,
        "tenant_security": tenant_security,
        "same_day_datetime": same_day,
    }


def snapshot_contract_probe() -> dict[str, Any]:
    from dms.agent.result_store import build_dataset_from_tool_results
    from dms.agent.schemas import dataset_source_hash

    output = {
        "ok": True,
        "resource": "sales",
        "aggregation": "average",
        "value_field": "final_price",
        "group_by": "company",
        "filters": {},
        "overall_value": 125.5,
        "total_value": 999999.0,
        "rows": [
            {
                "company": "Honda",
                "value": 125.5,
                "record_count": 2,
            }
        ],
    }
    dataset = build_dataset_from_tool_results(
        [
            {
                "tool": "aggregate_dms_records",
                "arguments": {},
                "output": output,
            }
        ],
        {"conversation_title": "Step 3 snapshot contract"},
    )
    if not dataset:
        raise AssertionError("snapshot dataset was not built")
    measure = dataset["measures"][0]
    total = dataset["totals"].get(measure["key"])
    if not _close_numbers(total, 125.5):
        raise AssertionError(
            "snapshot did not prefer overall_value"
        )
    row_value = dataset["rows"][0].get(measure["key"])
    if not isinstance(row_value, (int, float)):
        raise AssertionError(
            "snapshot row aggregate is not numeric"
        )
    source_hash = dataset_source_hash(
        dataset,
        ["aggregate_dms_records"],
    )
    if len(source_hash) != 64:
        raise AssertionError("snapshot source hash is invalid")
    return {
        "status": "pass",
        "measure": measure["key"],
        "total": total,
        "row_value_type": type(row_value).__name__,
        "source_hash_length": len(source_hash),
    }
