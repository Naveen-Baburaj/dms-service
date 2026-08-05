from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any

import frappe
from frappe.utils import add_days, get_datetime, now_datetime

from dms.agent.schemas import (
    canonicalise_dataset,
    dataset_source_hash,
    normalise_key,
)


SNAPSHOT_DOCTYPE = "DMS AI Result Snapshot"
SNAPSHOT_TTL_DAYS = 30


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _measure_spec(
    resource: str,
    aggregation: str,
    value_field: str | None,
) -> dict[str, Any]:
    if aggregation == "count":
        if resource == "sales":
            return {
                "key": "units_sold",
                "label": "Units Sold",
                "format": "integer",
            }
        return {
            "key": f"{normalise_key(resource)}_count",
            "label": (
                f"{resource.replace('_', ' ').title()} Count"
            ),
            "format": "integer",
        }

    value_key = normalise_key(value_field or "value")
    key = f"{value_key}_{aggregation}"
    label = (
        f"{str(value_field or 'Value').replace('_', ' ').title()} "
        f"{aggregation.title()}"
    )
    value_format = "decimal"

    if (
        aggregation == "sum"
        and resource == "sales"
        and value_field == "final_price"
    ):
        key = "revenue"
        label = "Revenue"
        value_format = "currency"
    elif (
        aggregation == "average"
        and resource == "sales"
        and value_field == "final_price"
    ):
        key = "average_sale_value"
        label = "Average Sale Value"
        value_format = "currency"
    elif value_field and any(
        token in value_field.lower()
        for token in ["amount", "price", "revenue", "total"]
    ):
        value_format = "currency"

    result = {
        "key": key,
        "label": label,
        "format": value_format,
    }
    if value_format == "currency":
        result["currency"] = "INR"
    return result


def _dimension_specs(keys: list[str]) -> list[dict[str, Any]]:
    result = []
    for key in keys:
        dimension_type = (
            "date"
            if (
                key
                in {
                    "month",
                    "date",
                    "creation",
                    "due_date",
                    "booking_date",
                }
                or key.endswith("_date")
            )
            else "category"
        )
        result.append(
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "type": dimension_type,
            }
        )
    return result


def _aggregate_dataset(
    entries: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        if entry.get("tool") != "aggregate_dms_records":
            continue
        output = entry.get("output") or {}
        if not isinstance(output, dict) or not output.get("ok"):
            continue
        key = _json(
            {
                "resource": output.get("resource"),
                "group_by": output.get("group_by"),
                "filters": output.get("filters") or {},
            }
        )
        groups[key].append(entry)

    if not groups:
        return None

    selected = max(
        groups.values(),
        key=lambda items: (
            len(items),
            sum(
                len(
                    (item.get("output") or {}).get("rows")
                    or []
                )
                for item in items
            ),
        ),
    )
    first_output = selected[0].get("output") or {}
    resource = str(first_output.get("resource") or "records")

    dimension_keys: list[str] = []
    priority = ["month", "company", "status", "model", "group"]
    discovered: set[str] = set()
    for entry in selected:
        for row in (
            (entry.get("output") or {}).get("rows") or []
        ):
            if not isinstance(row, dict):
                continue
            for key in row:
                if key not in {
                    "value",
                    "record_count",
                    "date_field",
                }:
                    discovered.add(normalise_key(key))
    for key in priority:
        if key in discovered:
            dimension_keys.append(key)
    dimension_keys.extend(
        sorted(discovered - set(dimension_keys))
    )
    if not dimension_keys:
        dimension_keys = ["group"]

    row_map: dict[tuple[str, ...], dict[str, Any]] = {}
    measures: list[dict[str, Any]] = []
    totals: dict[str, Any] = {}
    seen_measure_keys: set[str] = set()

    for entry in selected:
        output = entry.get("output") or {}
        measure = _measure_spec(
            resource,
            str(output.get("aggregation") or "count"),
            output.get("value_field"),
        )
        if measure["key"] in seen_measure_keys:
            continue
        seen_measure_keys.add(measure["key"])
        measures.append(measure)
        if "overall_value" in output:
            totals[measure["key"]] = output.get("overall_value")
        else:
            totals[measure["key"]] = output.get("total_value")

        for raw_row in output.get("rows") or []:
            if not isinstance(raw_row, dict):
                continue
            dimensions = {
                key: raw_row.get(
                    key,
                    "All" if key == "group" else None,
                )
                for key in dimension_keys
            }
            row_key = tuple(
                str(dimensions.get(key) or "")
                for key in dimension_keys
            )
            row = row_map.setdefault(row_key, dimensions)
            row[measure["key"]] = raw_row.get("value")

    rows = list(row_map.values())
    rows.sort(
        key=lambda row: tuple(
            str(row.get(key) or "")
            for key in dimension_keys
        )
    )

    title = str(
        plan.get("conversation_title")
        or f"{resource.replace('_', ' ').title()} analysis"
    )
    return canonicalise_dataset(
        {
            "resource": resource,
            "title": title,
            "dimensions": _dimension_specs(dimension_keys),
            "measures": measures,
            "rows": rows,
            "totals": totals,
            "filters": first_output.get("filters") or {},
        }
    )


def _query_dataset(
    entries: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = []
    for entry in entries:
        if entry.get("tool") != "query_dms_records":
            continue
        output = entry.get("output") or {}
        if (
            isinstance(output, dict)
            and output.get("ok")
        ):
            candidates.append(entry)
    if not candidates:
        return None

    selected = max(
        candidates,
        key=lambda item: len(
            (item.get("output") or {}).get("rows") or []
        ),
    )
    output = selected.get("output") or {}
    rows = [
        dict(row)
        for row in (output.get("rows") or [])
        if isinstance(row, dict)
    ]
    fields = [
        normalise_key(field)
        for field in (output.get("fields") or [])
    ]

    dimensions = []
    measures = []
    for field in fields:
        values = [
            row.get(field)
            for row in rows
            if row.get(field) is not None
        ]
        numeric = bool(values) and all(
            (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
            )
            for value in values
        )
        if numeric:
            value_format = (
                "currency"
                if any(
                    token in field
                    for token in ["amount", "price", "total"]
                )
                else "decimal"
            )
            item = {
                "key": field,
                "label": field.replace("_", " ").title(),
                "format": value_format,
            }
            if value_format == "currency":
                item["currency"] = "INR"
            measures.append(item)
        else:
            dimensions.append(
                {
                    "key": field,
                    "label": field.replace("_", " ").title(),
                    "type": (
                        "date"
                        if (
                            field.endswith("_date")
                            or field == "creation"
                        )
                        else "category"
                    ),
                }
            )

    totals = {}
    for measure in measures:
        values = [
            float(row.get(measure["key"]))
            for row in rows
            if isinstance(
                row.get(measure["key"]),
                (int, float),
            )
        ]
        totals[measure["key"]] = (
            sum(values) if values else None
        )

    return canonicalise_dataset(
        {
            "resource": (
                output.get("resource") or "records"
            ),
            "title": (
                plan.get("conversation_title")
                or "DMS records"
            ),
            "dimensions": dimensions,
            "measures": measures,
            "rows": rows,
            "totals": totals,
            "filters": output.get("filters") or {},
        }
    )


def build_dataset_from_tool_results(
    tool_results: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    entries = [
        entry
        for entry in tool_results
        if isinstance(entry, dict)
    ]
    return (
        _aggregate_dataset(entries, plan)
        or _query_dataset(entries, plan)
    )


def snapshot_to_dict(doc) -> dict[str, Any]:
    dataset = canonicalise_dataset(
        _loads(doc.dataset_json, {})
    )
    return {
        "id": doc.name,
        "conversation_id": doc.conversation_id,
        "owner_key": doc.owner_key,
        "scope_key": doc.scope_key,
        "company_id": doc.company_id,
        "company_name": doc.company_name,
        "resource": doc.resource,
        "title": doc.title,
        "dataset": dataset,
        "dimensions": _loads(
            doc.dimensions_json,
            dataset.get("dimensions") or [],
        ),
        "measures": _loads(
            doc.measures_json,
            dataset.get("measures") or [],
        ),
        "filters": _loads(
            doc.filters_json,
            dataset.get("filters") or {},
        ),
        "totals": _loads(
            doc.totals_json,
            dataset.get("totals") or {},
        ),
        "presentation": _loads(
            doc.presentation_json,
            {},
        ),
        "source_tool_names": _loads(
            doc.source_tool_names_json,
            [],
        ),
        "source_hash": doc.source_hash,
        "row_count": int(doc.row_count or 0),
        "created_from_message": doc.created_from_message,
        "status": doc.status,
        "expires_at": str(doc.expires_at or ""),
        "created_at": str(doc.creation or ""),
    }


def create_snapshot_from_tool_results(
    conversation_doc,
    plan: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    dataset = build_dataset_from_tool_results(
        tool_results,
        plan,
    )
    if not dataset:
        return None

    source_tool_names = list(
        dict.fromkeys(
            str(entry.get("tool"))
            for entry in tool_results
            if (
                isinstance(entry, dict)
                and entry.get("tool")
            )
        )
    )
    source_hash = dataset_source_hash(
        dataset,
        source_tool_names,
    )

    existing = frappe.get_all(
        SNAPSHOT_DOCTYPE,
        filters={
            "conversation_id": conversation_doc.name,
            "owner_key": conversation_doc.owner_key,
            "scope_key": conversation_doc.scope_key,
            "source_hash": source_hash,
            "status": "Active",
        },
        fields=["name"],
        order_by="creation desc",
        limit_page_length=1,
    )
    if existing:
        return snapshot_to_dict(
            frappe.get_doc(
                SNAPSHOT_DOCTYPE,
                existing[0]["name"],
            )
        )

    doc = frappe.get_doc(
        {
            "doctype": SNAPSHOT_DOCTYPE,
            "conversation_id": conversation_doc.name,
            "owner_key": conversation_doc.owner_key,
            "scope_key": conversation_doc.scope_key,
            "company_id": conversation_doc.company_id,
            "company_name": conversation_doc.company_name,
            "resource": dataset.get("resource"),
            "title": dataset.get("title"),
            "dataset_json": _json(dataset),
            "dimensions_json": _json(
                dataset.get("dimensions") or []
            ),
            "measures_json": _json(
                dataset.get("measures") or []
            ),
            "filters_json": _json(
                dataset.get("filters") or {}
            ),
            "totals_json": _json(
                dataset.get("totals") or {}
            ),
            "presentation_json": _json({}),
            "source_tool_names_json": _json(
                source_tool_names
            ),
            "source_hash": source_hash,
            "row_count": int(
                dataset.get("row_count") or 0
            ),
            "status": "Active",
            "expires_at": add_days(
                now_datetime(),
                SNAPSHOT_TTL_DAYS,
            ),
        }
    )
    doc.insert(ignore_permissions=True)
    return snapshot_to_dict(doc)


def load_snapshot(
    snapshot_id: str,
    conversation_doc,
) -> dict[str, Any]:
    if not snapshot_id:
        frappe.throw(
            "Result snapshot ID is required.",
            frappe.ValidationError,
        )

    try:
        doc = frappe.get_doc(
            SNAPSHOT_DOCTYPE,
            snapshot_id,
        )
    except Exception:
        frappe.throw(
            "Result snapshot not found.",
            frappe.DoesNotExistError,
        )

    if (
        doc.conversation_id != conversation_doc.name
        or doc.owner_key != conversation_doc.owner_key
        or doc.scope_key != conversation_doc.scope_key
    ):
        frappe.throw(
            "You do not have access to this result snapshot.",
            frappe.PermissionError,
        )

    if doc.status != "Active":
        frappe.throw(
            "Result snapshot is not active.",
            frappe.DoesNotExistError,
        )

    if (
        doc.expires_at
        and get_datetime(doc.expires_at) < now_datetime()
    ):
        frappe.throw(
            "Result snapshot has expired.",
            frappe.DoesNotExistError,
        )

    return snapshot_to_dict(doc)


def link_snapshot_to_message(
    snapshot_id: str,
    message_id: str,
    conversation_doc,
) -> None:
    snapshot = load_snapshot(
        snapshot_id,
        conversation_doc,
    )
    doc = frappe.get_doc(
        SNAPSHOT_DOCTYPE,
        snapshot["id"],
    )
    doc.created_from_message = message_id
    doc.save(ignore_permissions=True)


def archive_snapshots_for_conversation(
    conversation_doc,
) -> int:
    names = frappe.get_all(
        SNAPSHOT_DOCTYPE,
        filters={
            "conversation_id": conversation_doc.name,
            "owner_key": conversation_doc.owner_key,
            "scope_key": conversation_doc.scope_key,
            "status": "Active",
        },
        pluck="name",
    )
    for name in names:
        frappe.db.set_value(
            SNAPSHOT_DOCTYPE,
            name,
            "status",
            "Archived",
            update_modified=False,
        )
    return len(names)


def runtime_self_test() -> dict[str, Any]:
    from dms.agent.presentation import (
        detect_presentation_request,
        render_snapshot_response,
    )

    token = uuid.uuid4().hex
    base_doc = {
        "doctype": "DMS AI Conversation",
        "title": f"STEP2 SELF TEST {token}",
        "owner_key": f"owner-{token}",
        "owner_label": "step2-self-test",
        "scope_key": f"scope-{token}",
        "is_group_admin": 1,
        "memory_summary": "",
        "memory_state_json": "{}",
        "last_message_at": now_datetime(),
        "message_count": 0,
        "status": "Active",
    }

    try:
        conversation = frappe.get_doc(
            base_doc
        ).insert(ignore_permissions=True)
        other_conversation = frappe.get_doc(
            {
                **base_doc,
                "title": f"STEP2 OTHER CHAT {token}",
            }
        ).insert(ignore_permissions=True)
        other_owner = frappe.get_doc(
            {
                **base_doc,
                "title": f"STEP2 OTHER OWNER {token}",
                "owner_key": f"other-owner-{token}",
            }
        ).insert(ignore_permissions=True)

        filters = {
            "companies": ["Honda", "NEXA"],
            "statuses": [],
            "date_from": "2026-06-01",
            "date_to": "2026-07-31",
        }
        count_rows = [
            {
                "company": "Honda",
                "month": "2026-06",
                "value": 10,
                "record_count": 10,
            },
            {
                "company": "NEXA",
                "month": "2026-06",
                "value": 8,
                "record_count": 8,
            },
            {
                "company": "Honda",
                "month": "2026-07",
                "value": 12,
                "record_count": 12,
            },
            {
                "company": "NEXA",
                "month": "2026-07",
                "value": 9,
                "record_count": 9,
            },
        ]
        revenue_rows = [
            {
                "company": "Honda",
                "month": "2026-06",
                "value": 2000000,
                "record_count": 10,
            },
            {
                "company": "NEXA",
                "month": "2026-06",
                "value": 1600000,
                "record_count": 8,
            },
            {
                "company": "Honda",
                "month": "2026-07",
                "value": 2500000,
                "record_count": 12,
            },
            {
                "company": "NEXA",
                "month": "2026-07",
                "value": 1900000,
                "record_count": 9,
            },
        ]
        tool_results = [
            {
                "tool": "aggregate_dms_records",
                "arguments": {},
                "output": {
                    "ok": True,
                    "resource": "sales",
                    "aggregation": "count",
                    "value_field": None,
                    "group_by": "company_month",
                    "filters": filters,
                    "rows": count_rows,
                    "total_value": 39,
                },
            },
            {
                "tool": "aggregate_dms_records",
                "arguments": {},
                "output": {
                    "ok": True,
                    "resource": "sales",
                    "aggregation": "sum",
                    "value_field": "final_price",
                    "group_by": "company_month",
                    "filters": filters,
                    "rows": revenue_rows,
                    "total_value": 7000000,
                },
            },
        ]
        plan = {
            "conversation_title": (
                "Honda and NEXA sales"
            ),
            "metric": "count and revenue",
            "memory": {"chart_type": "line"},
        }
        snapshot = create_snapshot_from_tool_results(
            conversation,
            plan,
            tool_results,
        )
        if not snapshot:
            raise AssertionError(
                "Snapshot was not created"
            )

        loaded = load_snapshot(
            snapshot["id"],
            conversation,
        )
        dataset = loaded["dataset"]
        dimension_keys = [
            item["key"]
            for item in dataset["dimensions"]
        ]
        measure_keys = [
            item["key"]
            for item in dataset["measures"]
        ]

        same_hash = (
            dataset_source_hash(
                dataset,
                loaded["source_tool_names"],
            )
            == loaded["source_hash"]
        )

        new_chat_denied = False
        try:
            load_snapshot(
                snapshot["id"],
                other_conversation,
            )
        except frappe.PermissionError:
            new_chat_denied = True

        cross_owner_denied = False
        try:
            load_snapshot(
                snapshot["id"],
                other_owner,
            )
        except frappe.PermissionError:
            cross_owner_denied = True

        table_request = detect_presentation_request(
            "Show that exact saved result in table form"
        )
        table_response, table_view = (
            render_snapshot_response(
                loaded,
                (
                    "Show that exact saved result "
                    "in table form"
                ),
                table_request,
            )
        )
        line_response, line_view = (
            render_snapshot_response(
                loaded,
                (
                    "Show that exact saved result "
                    "as a line chart"
                ),
                {
                    "type": "line",
                    "presentation_only": True,
                },
            )
        )

        state = {
            "snapshot_created": bool(
                snapshot["id"]
            ),
            "source_hash_integrity": same_hash,
            "row_count": bool(
                dataset["row_count"]
            ),
            "month_dimension": (
                "month" in dimension_keys
            ),
            "company_dimension": (
                "company" in dimension_keys
            ),
            "units_measure": (
                "units_sold" in measure_keys
            ),
            "revenue_measure": (
                "revenue" in measure_keys
            ),
            "new_chat_denied": new_chat_denied,
            "cross_owner_denied": (
                cross_owner_denied
            ),
            "table_reuses_hash": (
                table_response[
                    "snapshot_source_hash"
                ]
                == loaded["source_hash"]
            ),
            "line_reuses_hash": (
                line_response[
                    "snapshot_source_hash"
                ]
                == loaded["source_hash"]
            ),
            "table_view": (
                table_view["type"] == "table"
            ),
            "line_view": (
                line_view["type"] == "line"
            ),
        }
        if not all(state.values()):
            raise AssertionError(
                f"Step 2 self-test failed: {state}"
            )
        return state
    finally:
        frappe.db.rollback()
