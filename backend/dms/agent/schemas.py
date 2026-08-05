from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SCHEMA_VERSION = 1
MAX_DATASET_ROWS = 5000
VALID_DIMENSION_TYPES = {"category", "date", "datetime", "text"}
VALID_MEASURE_FORMATS = {
    "integer",
    "decimal",
    "currency",
    "percentage",
}
VALID_VIEW_TYPES = {
    "table",
    "bar",
    "line",
    "pie",
    "area",
    "stacked_bar",
}


def normalise_key(value: Any, *, fallback: str = "field") -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text or fallback


def _plain_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonicalise_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(dataset, dict):
        raise ValueError("Analytical dataset must be an object")

    resource = normalise_key(dataset.get("resource"), fallback="records")
    title = str(dataset.get("title") or "DMS analytical result").strip()[:240]

    dimensions: list[dict[str, Any]] = []
    seen_dimensions: set[str] = set()
    for raw in dataset.get("dimensions") or []:
        if not isinstance(raw, dict):
            continue
        key = normalise_key(raw.get("key"))
        if key in seen_dimensions:
            continue
        seen_dimensions.add(key)
        dimension_type = str(raw.get("type") or "category")
        if dimension_type not in VALID_DIMENSION_TYPES:
            dimension_type = "category"
        dimensions.append(
            {
                "key": key,
                "label": str(
                    raw.get("label") or key.replace("_", " ").title()
                )[:140],
                "type": dimension_type,
            }
        )

    measures: list[dict[str, Any]] = []
    seen_measures: set[str] = set()
    for raw in dataset.get("measures") or []:
        if not isinstance(raw, dict):
            continue
        key = normalise_key(raw.get("key"))
        if key in seen_measures or key in seen_dimensions:
            continue
        seen_measures.add(key)
        value_format = str(raw.get("format") or "decimal")
        if value_format not in VALID_MEASURE_FORMATS:
            value_format = "decimal"
        item: dict[str, Any] = {
            "key": key,
            "label": str(
                raw.get("label") or key.replace("_", " ").title()
            )[:140],
            "format": value_format,
        }
        if value_format == "currency":
            item["currency"] = str(raw.get("currency") or "INR")[:12]
        measures.append(item)

    allowed_keys = [item["key"] for item in dimensions + measures]
    rows: list[dict[str, Any]] = []
    for raw in (dataset.get("rows") or [])[:MAX_DATASET_ROWS]:
        if not isinstance(raw, dict):
            continue
        rows.append(
            {
                key: _plain_value(raw.get(key))
                for key in allowed_keys
            }
        )

    totals: dict[str, int | float | None] = {}
    raw_totals = dataset.get("totals") or {}
    for measure in measures:
        value = raw_totals.get(measure["key"])
        if value is None:
            totals[measure["key"]] = None
            continue
        try:
            totals[measure["key"]] = float(value)
        except Exception:
            totals[measure["key"]] = None

    filters = dataset.get("filters") or {}
    if not isinstance(filters, dict):
        filters = {}

    return {
        "schema_version": SCHEMA_VERSION,
        "resource": resource,
        "title": title,
        "dimensions": dimensions,
        "measures": measures,
        "rows": rows,
        "totals": totals,
        "filters": filters,
        "row_count": len(rows),
    }


def dataset_source_hash(
    dataset: dict[str, Any],
    source_tool_names: list[str] | None = None,
) -> str:
    canonical = canonicalise_dataset(dataset)
    payload = {
        "dataset": canonical,
        "source_tool_names": sorted(
            str(name)
            for name in (source_tool_names or [])
            if name
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def schema_probe() -> dict[str, Any]:
    sample = canonicalise_dataset(
        {
            "resource": "sales",
            "title": "Sample",
            "dimensions": [
                {"key": "month", "label": "Month", "type": "date"},
                {
                    "key": "company",
                    "label": "Company",
                    "type": "category",
                },
            ],
            "measures": [
                {
                    "key": "units_sold",
                    "label": "Units Sold",
                    "format": "integer",
                },
                {
                    "key": "revenue",
                    "label": "Revenue",
                    "format": "currency",
                },
            ],
            "rows": [
                {
                    "month": "2026-07",
                    "company": "Honda",
                    "units_sold": 12,
                    "revenue": 2400000,
                }
            ],
            "totals": {
                "units_sold": 12,
                "revenue": 2400000,
            },
        }
    )
    return {
        "schema_version": sample["schema_version"],
        "dimensions": len(sample["dimensions"]),
        "measures": len(sample["measures"]),
        "rows": len(sample["rows"]),
        "hash_length": len(dataset_source_hash(sample, ["test"])),
    }
