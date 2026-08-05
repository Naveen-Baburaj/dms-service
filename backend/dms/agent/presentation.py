from __future__ import annotations

import re
from typing import Any

from dms.agent.schemas import VALID_VIEW_TYPES, canonicalise_dataset


LEGACY_ANALYTICAL_WIDGETS = {
    "sales_chart",
    "service_count_chart",
    "tenant_comparison_chart",
    "record_table",
    "generic_charts",
}


def detect_presentation_request(query: str) -> dict[str, Any] | None:
    text = str(query or "").strip().lower()
    if not text:
        return None

    view_type = None
    if "table" in text or "tabular" in text or "rows" in text:
        view_type = "table"
    elif "pie" in text or "donut" in text:
        view_type = "pie"
    elif "stacked" in text and ("bar" in text or "chart" in text):
        view_type = "stacked_bar"
    elif "area" in text and ("chart" in text or "graph" in text):
        view_type = "area"
    elif "line" in text and ("chart" in text or "graph" in text):
        view_type = "line"
    elif "bar" in text and ("chart" in text or "graph" in text):
        view_type = "bar"
    elif "chart" in text or "graph" in text or "visual" in text:
        view_type = "bar"

    if not view_type:
        return None

    referential = bool(
        re.search(
            r"\b(it|that|those|same|previous|above|saved|result|exact)\b",
            text,
        )
    )
    domain_terms = {
        "customer", "lead", "sale", "revenue", "invoice", "booking",
        "service", "inventory", "vehicle", "honda", "nexa", "jaguar",
        "month", "week", "year", "today", "yesterday",
    }
    words = re.findall(r"[a-z0-9]+", text)
    has_domain = any(term in text for term in domain_terms)

    if not referential and (has_domain or len(words) > 9):
        return None

    requested_measure = None
    if any(
        term in text
        for term in ["revenue", "amount", "value", "rupee"]
    ):
        requested_measure = "revenue"
    elif any(
        term in text
        for term in ["unit", "count", "number", "volume"]
    ):
        requested_measure = "count"
    elif "average" in text or "avg" in text:
        requested_measure = "average"

    return {
        "type": view_type,
        "requested_measure": requested_measure,
        "presentation_only": True,
    }


def _measure_for_request(
    dataset: dict[str, Any],
    requested_measure: str | None,
    plan_metric: str | None = None,
) -> dict[str, Any] | None:
    measures = dataset.get("measures") or []
    if not measures:
        return None

    text = f"{requested_measure or ''} {plan_metric or ''}".lower()

    if any(
        term in text
        for term in ["revenue", "amount", "value", "price"]
    ):
        for measure in measures:
            if (
                measure.get("format") == "currency"
                or any(
                    term in str(measure.get("key") or "").lower()
                    for term in ["revenue", "amount", "price", "value"]
                )
            ):
                return measure

    if any(
        term in text
        for term in ["count", "unit", "volume", "number"]
    ):
        for measure in measures:
            if (
                measure.get("format") == "integer"
                or "count" in str(measure.get("key") or "").lower()
                or "unit" in str(measure.get("key") or "").lower()
            ):
                return measure

    if "average" in text or "avg" in text:
        for measure in measures:
            if "average" in str(measure.get("key") or "").lower():
                return measure

    return measures[0]


def select_snapshot_view(
    snapshot: dict[str, Any],
    query: str,
    *,
    plan: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dataset = canonicalise_dataset(snapshot.get("dataset") or {})
    dimensions = dataset.get("dimensions") or []
    measures = dataset.get("measures") or []
    query_text = str(query or "").lower()
    memory = (plan or {}).get("memory") or {}

    view_type = str((request or {}).get("type") or "").strip()
    if not view_type:
        if "pie" in query_text or "donut" in query_text:
            view_type = "pie"
        elif "stacked" in query_text:
            view_type = "stacked_bar"
        elif "table" in query_text:
            view_type = "table"
        elif "area" in query_text:
            view_type = "area"
        elif "line" in query_text:
            view_type = "line"
        elif "bar" in query_text:
            view_type = "bar"
        else:
            remembered = str(memory.get("chart_type") or "")
            if remembered in VALID_VIEW_TYPES:
                view_type = remembered

    if not view_type:
        dimension_keys = {item.get("key") for item in dimensions}
        if "month" in dimension_keys and measures:
            view_type = "line"
        elif measures:
            view_type = "bar"
        else:
            view_type = "table"

    if view_type not in VALID_VIEW_TYPES:
        view_type = "table"
    if not measures:
        view_type = "table"

    requested_measure = (request or {}).get("requested_measure")
    measure = _measure_for_request(
        dataset,
        str(requested_measure or "") or None,
        str((plan or {}).get("metric") or "") or None,
    )

    dimension_keys = [
        item.get("key")
        for item in dimensions
        if item.get("key")
    ]
    date_keys = [
        item.get("key")
        for item in dimensions
        if (
            item.get("type") in {"date", "datetime"}
            or item.get("key") in {"month", "date", "creation"}
        )
    ]
    company_key = next(
        (key for key in dimension_keys if key == "company"),
        None,
    )

    x_field = None
    series_field = None
    if view_type == "pie":
        x_field = company_key or (
            dimension_keys[0] if dimension_keys else None
        )
    elif view_type != "table":
        x_field = (
            date_keys[0]
            if date_keys
            else (dimension_keys[0] if dimension_keys else None)
        )
        series_field = next(
            (
                key
                for key in dimension_keys
                if key != x_field and key == "company"
            ),
            None,
        )
        if series_field is None:
            series_field = next(
                (key for key in dimension_keys if key != x_field),
                None,
            )

    value_field = measure.get("key") if measure else None
    measure_label = measure.get("label") if measure else "Records"

    return {
        "type": view_type,
        "x_field": x_field,
        "series_field": series_field,
        "value_field": value_field,
        "title": (
            f"{dataset.get('title') or 'DMS result'} — {measure_label}"
        ),
    }


def analytical_view_payload(
    snapshot: dict[str, Any],
    view: dict[str, Any],
    *,
    reused: bool,
) -> dict[str, Any]:
    dataset = canonicalise_dataset(snapshot.get("dataset") or {})
    return {
        "snapshot_id": snapshot.get("id"),
        "source_hash": snapshot.get("source_hash"),
        "title": dataset.get("title"),
        "resource": dataset.get("resource"),
        "dataset": dataset,
        "view": view,
        "reused": bool(reused),
        "data_source": "dms_ai_result_snapshot",
    }


def attach_snapshot_to_response(
    data: dict[str, Any],
    snapshot: dict[str, Any],
    view: dict[str, Any],
    *,
    reused: bool,
) -> dict[str, Any]:
    payloads = data.setdefault("widget_payloads", {})
    shown = [
        widget
        for widget in (data.get("widgets_to_show") or [])
        if widget not in LEGACY_ANALYTICAL_WIDGETS
    ]
    for widget in LEGACY_ANALYTICAL_WIDGETS:
        payloads.pop(widget, None)

    shown.append("analytical_view")
    data["widgets_to_show"] = list(dict.fromkeys(shown))
    data["widgets_to_hide"] = [
        widget
        for widget in (data.get("widgets_to_hide") or [])
        if widget != "analytical_view"
    ]
    payloads["analytical_view"] = analytical_view_payload(
        snapshot,
        view,
        reused=reused,
    )
    data["active_snapshot_id"] = snapshot.get("id")
    data["snapshot_source_hash"] = snapshot.get("source_hash")

    other = (
        data.setdefault("filters_applied", {})
        .setdefault("other", {})
    )
    other["snapshot_id"] = snapshot.get("id")
    other["snapshot_source_hash"] = snapshot.get("source_hash")
    other["snapshot_reused"] = bool(reused)
    other["presentation_only"] = bool(reused)
    other["presentation_type"] = view.get("type")
    return data


def render_snapshot_response(
    snapshot: dict[str, Any],
    query: str,
    request: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset = canonicalise_dataset(snapshot.get("dataset") or {})
    view = select_snapshot_view(
        snapshot,
        query,
        request=request,
    )
    label = str(view.get("type") or "table").replace("_", " ")
    data = {
        "intent": "snapshot_presentation",
        "filters_applied": {
            "metric": view.get("value_field"),
            "time_range": (
                dataset.get("filters") or {}
            ).get("time_range"),
            "tenant_id": (
                snapshot.get("company_id")
                or "all_allowed_tenants"
            ),
            "other": {
                "answer_type": "saved_result_presentation",
                "snapshot_id": snapshot.get("id"),
                "snapshot_source_hash": snapshot.get("source_hash"),
                "snapshot_reused": True,
                "presentation_only": True,
                "presentation_type": view.get("type"),
                "agentic_mode": False,
                "agentic_steps": 0,
                "agentic_tool_calls": 0,
                "agentic_tool_trace": [],
            },
        },
        "widgets_to_show": ["analytical_view"],
        "widgets_to_hide": sorted(LEGACY_ANALYTICAL_WIDGETS),
        "text_response": (
            f"Showing the exact saved result as a {label}. "
            "The underlying rows, filters, totals, and source hash "
            "are unchanged."
        ),
        "widget_payloads": {
            "analytical_view": analytical_view_payload(
                snapshot,
                view,
                reused=True,
            )
        },
        "active_snapshot_id": snapshot.get("id"),
        "snapshot_source_hash": snapshot.get("source_hash"),
    }
    return data, view
