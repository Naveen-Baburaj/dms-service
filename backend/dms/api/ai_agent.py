"""
AI Dashboard Agent API for DMS.

Endpoint:
POST /api/method/dms.api.ai_agent.query

Design:
- Gemini is used as the semantic router/planner.
- Tenant security is deterministic and enforced before data access.
- Database access is metadata-safe: only real DocType fields are selected.
- The same Frappe DocType data used by dashboard pages is used by chat widgets.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import frappe
from frappe.utils import add_months, getdate, nowdate

from dms.api.knowledge_guard import build_knowledge_response
from dms.utils.permissions import get_user_company, is_group_admin
from dms.utils.response import success, error


ALL_WIDGETS = [
    "sales_chart",
    "service_count_chart",
    "inventory_table",
    "tenant_comparison_chart",
    "record_table",
    "generic_charts",
]

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ENABLE_GEMINI_INTENT = os.getenv("ENABLE_GEMINI_INTENT", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

VALID_INTENTS = {
    "sales_analysis",
    "service_analysis",
    "inventory_analysis",
    "tenant_comparison",
    "dashboard_charts",
    "record_lookup",
    "knowledge_lookup",
    "out_of_scope",
}

COMPANY_NAMES = {
    "honda": "Honda",
    "nexa": "NEXA",
    "jaguar": "Jaguar",
}

COMPANY_ALIASES = {
    "honda": "Honda",
    "toyota": "Honda",
    "nexa": "NEXA",
    "suzuki": "NEXA",
    "jaguar": "Jaguar",
    "hyundai": "Jaguar",
    "group": None,
    "all": None,
}

RECORD_RESOURCES: dict[str, dict[str, Any]] = {
    "leads": {
        "doctype": "DMS Lead",
        "title": "Leads",
        "keywords": ["lead", "leads", "enquiry", "enquiries", "prospect", "prospects"],
        "search_fields": ["lead_name", "email", "mobile_no", "vehicle_interest", "source", "status"],
        "columns": [
            {"key": "lead_name", "label": "Lead"},
            {"key": "mobile_no", "label": "Mobile"},
            {"key": "vehicle_interest", "label": "Interest"},
            {"key": "source", "label": "Source"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "lead_name", "mobile_no", "email", "vehicle_interest", "source", "status", "creation"],
    },
    "customers": {
        "doctype": "DMS Customer",
        "title": "Customers",
        "keywords": ["customer", "customers", "client", "clients"],
        "search_fields": ["customer_name", "email", "mobile_no", "city", "status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "mobile_no", "label": "Mobile"},
            {"key": "customer_type", "label": "Type"},
            {"key": "total_purchases", "label": "Purchases"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "mobile_no", "email", "customer_type", "total_purchases", "status", "creation"],
    },
    "sales": {
        "doctype": "DMS Vehicle Sale",
        "title": "Vehicle Sales",
        "keywords": ["sale", "sales", "sold", "delivery", "deliveries", "revenue"],
        "search_fields": ["customer_name", "model", "variant", "payment_mode", "status", "invoice_no"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "final_price", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "payment_mode", "status", "invoice_no", "creation"],
    },
    "bookings": {
        "doctype": "DMS Booking",
        "title": "Bookings",
        "keywords": ["booking", "bookings", "reserved", "reservation"],
        "search_fields": ["customer_name", "model", "variant", "status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "booking_amount", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "model", "variant", "booking_amount", "booking_date", "expected_delivery", "status", "creation"],
    },
    "test_drives": {
        "doctype": "DMS Test Drive",
        "title": "Test Drives",
        "keywords": ["test drive", "test drives", "drive", "drives"],
        "search_fields": ["contact_name", "mobile_no", "model", "status"],
        "columns": [
            {"key": "contact_name", "label": "Contact"},
            {"key": "mobile_no", "label": "Mobile"},
            {"key": "model", "label": "Model"},
            {"key": "scheduled_date", "label": "Date"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "contact_name", "mobile_no", "model", "scheduled_date", "scheduled_time", "rating", "status", "creation"],
    },
    "service_jobs": {
        "doctype": "DMS Service Job",
        "title": "Service Jobs",
        "keywords": ["service job", "service jobs", "job card", "job cards", "services", "service"],
        "search_fields": ["customer_name", "vehicle_reg_no", "model", "service_type", "status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "vehicle_reg_no", "label": "Reg No"},
            {"key": "service_type", "label": "Type"},
            {"key": "total_amount", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "vehicle_reg_no", "model", "service_type", "total_amount", "status", "creation"],
    },
    "invoices": {
        "doctype": "DMS Invoice",
        "title": "Invoices",
        "keywords": ["invoice", "invoices", "bill", "bills", "payment", "payments"],
        "search_fields": ["customer_name", "invoice_type", "reference_doc", "payment_status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "invoice_type", "label": "Type"},
            {"key": "total_amount", "label": "Total"},
            {"key": "payment_status", "label": "Payment"},
            {"key": "due_date", "label": "Due"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "invoice_type", "total_amount", "payment_status", "due_date", "reference_doc", "creation"],
    },
    "vehicles": {
        "doctype": "DMS Vehicle",
        "title": "Vehicles",
        "keywords": ["vehicle", "vehicles", "inventory", "stock", "cars"],
        "search_fields": ["vehicle_name", "model", "variant", "color", "stock_status", "chassis_no"],
        "columns": [
            {"key": "vehicle_name", "label": "Vehicle"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "color", "label": "Color"},
            {"key": "stock_status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "vehicle_name", "model", "variant", "color", "stock_status", "creation"],
    },
}

SMART_STOPWORDS = {
    "show", "list", "display", "give", "get", "find", "search", "view", "open",
    "the", "a", "an", "of", "for", "to", "me", "all", "latest", "recent",
    "record", "records", "data", "table", "details", "detail", "with", "by",
    "please", "want", "need", "i", "admin", "tenant", "company", "companies",
    "chart", "charts", "graph", "graphs", "dashboard", "relevant",
}

RESOURCE_WORDS = {
    word
    for config in RECORD_RESOURCES.values()
    for keyword in config["keywords"]
    for word in keyword.split()
}


def _request_json() -> dict[str, Any]:
    if frappe.form_dict:
        if frappe.form_dict.get("query"):
            data = {"query": frappe.form_dict.get("query")}
            if frappe.form_dict.get("conversation_context"):
                data["conversation_context"] = frappe.form_dict.get("conversation_context")
            return data

        if frappe.form_dict.get("data"):
            try:
                return json.loads(frappe.form_dict.get("data") or "{}")
            except Exception:
                return {}

    try:
        raw = frappe.request.get_data(as_text=True)
        if raw:
            return json.loads(raw)
    except Exception:
        return {}

    return {}


def _header(name: str) -> str | None:
    try:
        return frappe.get_request_header(name)
    except Exception:
        return None


def _normalize_key(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _company_name_from_alias(value: str | None) -> str | None:
    key = _normalize_key(value)
    if not key:
        return None
    if key in COMPANY_ALIASES:
        return COMPANY_ALIASES[key]
    if key in COMPANY_NAMES:
        return COMPANY_NAMES[key]
    return value


def _company_id_from_name(company_name: str | None) -> str | None:
    if not company_name:
        return None
    try:
        return frappe.db.get_value("DMS Company", {"company_name": company_name}, "name")
    except Exception:
        return None


def _company_name_from_id(company_id: str | None) -> str | None:
    if not company_id:
        return None
    try:
        return frappe.db.get_value("DMS Company", company_id, "company_name") or company_id
    except Exception:
        return company_id


def _is_admin_from_dev_header() -> bool:
    return _header("x-user-role") == "service_centre_admin"


def _dev_company_from_header() -> str | None:
    role = _header("x-user-role")
    if role == "service_centre_admin":
        return None
    return _company_name_from_alias(_header("x-tenant-id"))


def _is_admin() -> bool:
    try:
        if is_group_admin():
            return True
    except Exception:
        pass
    return _is_admin_from_dev_header()


def _user_company_scope() -> tuple[str | None, str | None]:
    if _is_admin():
        return None, None

    try:
        company_id = get_user_company()
        if company_id and company_id != "__none__":
            return company_id, _company_name_from_id(company_id)
    except Exception:
        pass

    company_name = _dev_company_from_header()
    company_id = _company_id_from_name(company_name)
    return company_id, company_name


def _mentioned_company_names(query: str) -> set[str]:
    q = query.lower()
    mentioned: set[str] = set()
    for alias, company_name in COMPANY_ALIASES.items():
        if not alias or company_name is None:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", q):
            mentioned.add(company_name)
    return mentioned


def _smart_company_mentions(query: str) -> list[str]:
    found: list[str] = []
    for company in _mentioned_company_names(query):
        if company and company not in found:
            found.append(company)
    order = {"Honda": 0, "NEXA": 1, "Jaguar": 2}
    found.sort(key=lambda name: order.get(name, 99))
    return found


def _requests_cross_company_scope(query: str) -> bool:
    q = query.lower()
    cross_terms = [
        "all companies",
        "all tenants",
        "all brands",
        "all dealerships",
        "group data",
        "group-wide",
        "cross company",
        "cross-company",
        "cross tenant",
        "cross-tenant",
        "compare companies",
        "compare tenants",
        "compare brands",
        "compare honda",
        "compare nexa",
        "compare jaguar",
    ]
    return any(term in q for term in cross_terms)


def _should_deny_cross_tenant_request(query: str) -> bool:
    if _is_admin():
        return False

    _, company_name = _user_company_scope()
    allowed_companies = {company_name} if company_name else set()
    mentioned_companies = _mentioned_company_names(query)

    if mentioned_companies and not mentioned_companies.issubset(allowed_companies):
        return True

    if _requests_cross_company_scope(query):
        return True

    return False


def _is_knowledge_lookup_query(query: str) -> bool:
    q = query.lower()
    knowledge_terms = [
        "policy", "policies", "rule", "rules", "guideline", "guidelines",
        "document", "documents", "doc", "docs", "knowledge", "manual",
        "sop", "procedure", "process", "access", "permission", "permissions",
        "allowed", "not allowed", "can i", "can user", "what can", "what is allowed",
    ]
    return any(term in q for term in knowledge_terms)


def _resolve_company_scope(query: str, route: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    if not _is_admin():
        return _user_company_scope()

    route_companies = []
    if route and isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in route_companies:
                route_companies.append(resolved)

    if len(route_companies) == 1:
        company_name = route_companies[0]
        return _company_id_from_name(company_name), company_name

    mentioned = _smart_company_mentions(query)
    if len(mentioned) == 1:
        company_name = mentioned[0]
        return _company_id_from_name(company_name), company_name

    return None, None


def _scope_filters_for_query(query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    if not _is_admin():
        company_id, company_name = _user_company_scope()
        return ({"company_id": company_id} if company_id else {}, company_name or "your company")

    companies: list[str] = []
    if route and isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in companies:
                companies.append(resolved)

    if not companies:
        companies = _smart_company_mentions(query)

    company_ids = [_company_id_from_name(company) for company in companies]
    company_ids = [company_id for company_id in company_ids if company_id]

    if len(company_ids) == 1:
        return {"company_id": company_ids[0]}, companies[0]

    if len(company_ids) > 1:
        return {"company_id": ["in", company_ids]}, " and ".join(companies)

    return {}, "all allowed companies"


def _safe_json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _is_followup_query(query: str) -> bool:
    q = query.lower().strip()
    return any(
        term in q
        for term in [
            "i meant", "i mean", "that one", "those", "it", "same",
            "previous", "above", "that data", "that chart", "that table",
        ]
    )


def _routing_query(user_query: str, conversation_context: str | None) -> str:
    if conversation_context and _is_followup_query(user_query):
        return f"{conversation_context}\nCurrent clarification: {user_query}"
    return user_query


@lru_cache(maxsize=256)
def _llm_smart_route(query: str) -> dict[str, Any]:
    if not ENABLE_GEMINI_INTENT:
        return {}

    api_key = os.getenv("GEMINI_API_KEY") or frappe.conf.get("gemini_api_key") or frappe.conf.get("GEMINI_API_KEY")
    if not api_key:
        return {}

    try:
        from google import genai
        from google.genai import types
    except Exception:
        return {}

    prompt = f"""
You are the semantic router for a Dealer Management System dashboard chatbot.

Return only JSON. No markdown.

Supported intents:
- record_lookup: rows/details/list/search from database tables
- dashboard_charts: charts, graphs, widgets, visualizations, available charts
- tenant_comparison: comparison between companies
- sales_analysis
- service_analysis
- inventory_analysis
- knowledge_lookup
- out_of_scope

Supported resources:
- leads
- customers
- sales
- bookings
- test_drives
- service_jobs
- invoices
- vehicles

Extract:
- intent
- resource
- companies: array of Honda, NEXA, Jaguar
- month_limit: integer or null
- search_text: customer/person/model/search phrase or null
- wants_all_charts: boolean
- confidence: 0 to 1

Examples:
- "invoice for diya kuiren" -> record_lookup, invoices, search_text "diya kuiren"
- "show invoice of arjun pillai" -> record_lookup, invoices, search_text "arjun pillai"
- "compare sales of honda and nexa" -> tenant_comparison, companies ["Honda", "NEXA"]
- "show all charts we have with last 4 months" -> dashboard_charts, wants_all_charts true, month_limit 4
- "list the leads" -> record_lookup, leads
- "show only nexa sales chart" -> sales_analysis, companies ["NEXA"]

User query:
{query}
""".strip()

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "resource": {"type": "string", "nullable": True},
            "companies": {"type": "array", "items": {"type": "string"}},
            "month_limit": {"type": "integer", "nullable": True},
            "search_text": {"type": "string", "nullable": True},
            "wants_all_charts": {"type": "boolean"},
            "confidence": {"type": "number"},
        },
        "required": ["intent"],
    }

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return _safe_json_loads(getattr(response, "text", None))
    except Exception:
        return {}


def _rule_based_detect_intent(query: str) -> str:
    q = query.lower()

    if _is_chart_query(query):
        return "dashboard_charts"

    if _detect_record_resource(query):
        return "record_lookup"

    if any(term in q for term in ["compare", "comparison", "across tenants", "across companies", "all tenants", "all companies", "cross tenant", "cross-tenant", "group"]):
        return "tenant_comparison"

    if any(word in q for word in ["sales", "revenue", "income"]):
        return "sales_analysis"

    if any(word in q for word in ["service", "servicing", "appointment", "appointments", "job", "jobs"]):
        return "service_analysis"

    if any(word in q for word in ["inventory", "stock", "vehicle", "vehicles", "parts", "spares"]):
        return "inventory_analysis"

    return "out_of_scope"


def _detect_intent(query: str, route: dict[str, Any] | None = None) -> str:
    if route and route.get("intent") in VALID_INTENTS:
        return str(route["intent"])
    return _rule_based_detect_intent(query)


def _smart_month_limit(query: str, route: dict[str, Any] | None = None) -> int | None:
    if route:
        value = route.get("month_limit")
        if isinstance(value, int) and value > 0:
            return min(value, 24)

    match = re.search(r"last\s+(\d+)\s+months?", query.lower())
    if match:
        return min(int(match.group(1)), 24)

    return None


def _month_window(month_limit: int | None) -> tuple[str | None, str | None]:
    if not month_limit:
        return None, None
    today = getdate(nowdate())
    start_date = add_months(today.replace(day=1), -(month_limit - 1)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    return start_date, end_date


def _month_labels(month_limit: int) -> list[str]:
    today = getdate(nowdate()).replace(day=1)
    return [add_months(today, -(month_limit - index - 1)).strftime("%Y-%m") for index in range(month_limit)]


def _month_label(value: Any) -> str:
    if not value:
        return ""
    try:
        return getdate(value).strftime("%Y-%m")
    except Exception:
        return str(value)[:7]


def _hidden_widgets(visible_widgets: list[str]) -> list[str]:
    return [widget_id for widget_id in ALL_WIDGETS if widget_id not in visible_widgets]


def _base_response(
    intent: str,
    metric: str | None,
    time_range: str | None,
    company_id: str | None,
    company_name: str | None,
    widgets_to_show: list[str],
    text_response: str,
    widget_payloads: dict[str, Any],
    other: dict[str, Any] | None = None,
) -> dict[str, Any]:
    final_other = {"data_source": "database"}
    if other:
        final_other.update(other)
    if company_name:
        final_other["tenant_display_name"] = company_name

    return {
        "intent": intent,
        "filters_applied": {
            "metric": metric,
            "time_range": time_range,
            "tenant_id": company_id or "all_allowed_tenants",
            "other": final_other,
        },
        "widgets_to_show": widgets_to_show,
        "widgets_to_hide": _hidden_widgets(widgets_to_show),
        "text_response": text_response,
        "widget_payloads": widget_payloads,
    }


def _no_data_response(intent: str, metric: str | None, time_range: str | None, company_id: str | None, company_name: str | None, message: str) -> dict[str, Any]:
    return _base_response(
        intent=intent,
        metric=metric,
        time_range=time_range,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=[],
        text_response=message,
        widget_payloads={},
        other={"error": "no_database_records"},
    )


def _database_sales_records(company_id: str | None, month_limit: int | None) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {"status": ["!=", "Cancelled"]}
    if company_id:
        filters["company_id"] = company_id

    start_date, end_date = _month_window(month_limit)
    if start_date and end_date:
        filters["creation"] = ["between", [start_date, end_date]]

    return frappe.get_all(
        "DMS Vehicle Sale",
        filters=filters,
        fields=_existing_fields("DMS Vehicle Sale", ["name", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "status", "creation"]),
        order_by="creation asc",
    )


def _database_service_records(company_id: str | None, month_limit: int | None) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if company_id:
        filters["company_id"] = company_id

    start_date, end_date = _month_window(month_limit)
    if start_date and end_date:
        filters["creation"] = ["between", [start_date, end_date]]

    return frappe.get_all(
        "DMS Service Job",
        filters=filters,
        fields=_existing_fields("DMS Service Job", ["name", "company_id", "company_name", "customer_name", "service_type", "total_amount", "status", "creation"]),
        order_by="creation asc",
    )


def _database_inventory_records(company_id: str | None) -> list[dict[str, Any]]:
    filters: dict[str, Any] = {}
    if company_id:
        filters["company_id"] = company_id

    return frappe.get_all(
        "DMS Vehicle",
        filters=filters,
        fields=_existing_fields("DMS Vehicle", ["name", "company_id", "company_name", "vehicle_name", "model", "variant", "color", "stock_status", "creation"]),
        order_by="modified desc",
    )


def _aggregate_database_monthly(rows: list[dict[str, Any]], value_field: str, count_mode: bool = False, month_limit: int | None = None) -> dict[str, Any]:
    labels = _month_labels(month_limit) if month_limit else []
    monthly: dict[str, float] = defaultdict(float)

    for label in labels:
        monthly[label] = 0.0

    for row in rows:
        month = _month_label(row.get("creation"))
        if labels and month not in monthly:
            continue
        monthly[month] += 1 if count_mode else float(row.get(value_field) or 0)

    final_labels = labels if labels else sorted(monthly.keys())
    series = [monthly[label] for label in final_labels]
    total = sum(series)

    highest_month = None
    if final_labels:
        peak_index = max(range(len(final_labels)), key=lambda index: series[index])
        highest_month = {"month": final_labels[peak_index], value_field: series[peak_index]}

    return {"labels": final_labels, "series": series, "total": total, "highest_month": highest_month}


def _detect_record_resource(query: str, route: dict[str, Any] | None = None) -> str | None:
    if route and route.get("resource") in RECORD_RESOURCES:
        return str(route["resource"])

    q = query.lower()
    for resource, config in RECORD_RESOURCES.items():
        if any(keyword in q for keyword in config["keywords"]):
            return resource

    return None


def _is_chart_query(query: str, route: dict[str, Any] | None = None) -> bool:
    if route and (route.get("intent") == "dashboard_charts" or route.get("wants_all_charts")):
        return True

    q = query.lower()
    chart_terms = [
        "chart", "charts", "graph", "graphs", "visual", "visualization",
        "widget", "widgets", "all charts", "available charts", "historical chart",
        "trend", "trends",
    ]
    return any(term in q for term in chart_terms)


def _extract_search_text(query: str, resource: str, route: dict[str, Any] | None = None) -> str | None:
    if route and route.get("search_text"):
        value = str(route["search_text"]).strip()
        if value:
            return value

    q = query.lower().strip()

    patterns = [
        r"(?:for|of|named|name|called)\s+([a-z][a-z\s.]+)$",
        r"(?:invoice|lead|customer|booking|sale|service|vehicle)\s+(?:for|of)\s+([a-z][a-z\s.]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate

    words = re.findall(r"[a-zA-Z]+", q)
    cleaned = []

    for word in words:
        normalized = word.lower()
        if normalized in SMART_STOPWORDS:
            continue
        if normalized in RESOURCE_WORDS:
            continue
        if normalized in COMPANY_ALIASES:
            continue
        cleaned.append(word)

    if cleaned:
        candidate = " ".join(cleaned).strip()
        return candidate if len(candidate) >= 2 else None

    return None


def _existing_fields(doctype: str, fields: list[str]) -> list[str]:
    meta = frappe.get_meta(doctype)
    system_fields = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}
    selected = [field for field in fields if field in system_fields or meta.has_field(field)]

    for field in ["name", "creation"]:
        if field not in selected:
            selected.append(field)

    return selected


def _row_text(row: dict[str, Any], fields: list[str]) -> str:
    return " ".join(str(row.get(field) or "") for field in fields).lower()


def _filter_rows_by_search(rows: list[dict[str, Any]], fields: list[str], search_text: str | None) -> list[dict[str, Any]]:
    if not search_text:
        return rows

    needle = search_text.lower().strip()
    if not needle:
        return rows

    exact = [row for row in rows if needle in _row_text(row, fields)]
    if exact:
        return exact

    scored = []
    for row in rows:
        field_scores = []
        for field in fields:
            value = str(row.get(field) or "").lower()
            if not value:
                continue
            field_scores.append(SequenceMatcher(None, needle, value).ratio())
            for token in needle.split():
                field_scores.append(SequenceMatcher(None, token, value).ratio())

        best = max(field_scores, default=0)
        if best >= 0.55:
            scored.append((best, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored]


def _record_table_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    resource = _detect_record_resource(query, route)
    if not resource:
        return _build_out_of_scope_response()

    config = RECORD_RESOURCES[resource]
    doctype = config["doctype"]
    fields = _existing_fields(doctype, config["fields"])
    filters, display_scope = _scope_filters_for_query(query, route)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=200,
    )

    search_text = _extract_search_text(query, resource, route)
    rows = _filter_rows_by_search(rows, config["search_fields"], search_text)

    total_after_filter = len(rows)
    rows = rows[:10]

    enriched_rows = []
    for row in rows:
        item = dict(row)
        item["id"] = item.get("name")
        if item.get("creation"):
            item["created_at"] = str(item.get("creation"))
        if item.get("company_id") and not item.get("company_name"):
            item["company_name"] = _company_name_from_id(item.get("company_id"))
        enriched_rows.append(item)

    if search_text and total_after_filter == 0:
        message = f"No matching {config['title'].lower()} found for '{search_text}' in {display_scope}."
    elif search_text:
        message = f"Here are the matching {config['title'].lower()} for '{search_text}' in {display_scope}. Showing {len(enriched_rows)} of {total_after_filter} matched database record(s)."
    else:
        message = f"Here are the latest {config['title'].lower()} for {display_scope}. Showing {len(enriched_rows)} of {total_after_filter} database record(s)."

    company_id, company_name = _resolve_company_scope(query, route)
    return _base_response(
        intent="record_lookup",
        metric=resource,
        time_range="latest records",
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["record_table"],
        text_response=message,
        widget_payloads={
            "record_table": {
                "title": config["title"],
                "resource": resource,
                "doctype": doctype,
                "columns": config["columns"],
                "rows": enriched_rows,
                "total": total_after_filter,
                "search_text": search_text,
                "data_source": "database",
            }
        },
        other={"data_source": "database", "doctype": doctype, "search_text": search_text},
    )


def _build_cross_tenant_denial_response(query: str) -> dict[str, Any]:
    company_id, company_name = _user_company_scope()
    display_name = company_name or "your company"
    return _base_response(
        intent="unauthorized",
        metric=None,
        time_range=None,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=[],
        text_response=f"You only have access to {display_name} information. I cannot show or discuss data from other companies.",
        widget_payloads={},
        other={"access_decision": "denied", "reason": "cross_tenant_request", "mentioned_companies": sorted(_mentioned_company_names(query))},
    )


def _build_sales_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    month_limit = _smart_month_limit(query, route)
    company_id, company_name = _resolve_company_scope(query, route)
    time_text = f"the last {month_limit} months" if month_limit else "all available months"
    rows = _database_sales_records(company_id, month_limit)
    display_name = company_name or "all allowed companies"

    if not rows:
        return _no_data_response("sales_analysis", "sales", time_text, company_id, company_name, f"No sales data was found in the DMS database for {display_name} over {time_text}.")

    summary = _aggregate_database_monthly(rows, "final_price", month_limit=month_limit)
    highest = summary["highest_month"]
    highest_month = {"month": highest["month"], "sales": highest["final_price"]} if highest else None

    text_response = f"Total sales for {display_name} over {time_text} were ₹{summary['total']:,.0f}."
    if highest_month:
        text_response += f" The highest month was {highest_month['month']} with ₹{highest_month['sales']:,.0f}."

    return _base_response(
        intent="sales_analysis",
        metric="sales",
        time_range=time_text,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["sales_chart"],
        text_response=text_response,
        widget_payloads={"sales_chart": {"labels": summary["labels"], "series": summary["series"], "total": summary["total"], "highest_month": highest_month}},
    )


def _build_service_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    month_limit = _smart_month_limit(query, route)
    company_id, company_name = _resolve_company_scope(query, route)
    time_text = f"the last {month_limit} months" if month_limit else "all available months"
    rows = _database_service_records(company_id, month_limit)
    display_name = company_name or "all allowed companies"

    if not rows:
        return _no_data_response("service_analysis", "service_count", time_text, company_id, company_name, f"No service data was found in the DMS database for {display_name} over {time_text}.")

    summary = _aggregate_database_monthly(rows, "name", count_mode=True, month_limit=month_limit)
    return _base_response(
        intent="service_analysis",
        metric="service_count",
        time_range=time_text,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["service_count_chart"],
        text_response=f"Total service records for {display_name} over {time_text} were {summary['total']:,.0f}.",
        widget_payloads={"service_count_chart": {"labels": summary["labels"], "series": summary["series"], "total": summary["total"]}},
    )


def _build_inventory_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    company_id, company_name = _resolve_company_scope(query, route)
    rows = _database_inventory_records(company_id)
    display_name = company_name or "all allowed companies"

    if not rows:
        return _no_data_response("inventory_analysis", "stock", "current", company_id, company_name, f"No inventory data was found in the DMS database for {display_name}.")

    enriched_rows = []
    stock_status_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        tenant_name = _company_name_from_id(row.get("company_id")) or "Unknown"
        stock_status = row.get("stock_status") or "Unknown"
        stock_status_counts[stock_status] += 1
        enriched_rows.append({
            "tenant_id": row.get("company_id"),
            "tenant_name": tenant_name,
            "vehicle_name": row.get("vehicle_name"),
            "model": row.get("model"),
            "variant": row.get("variant"),
            "stock_status": stock_status,
            "category": row.get("vehicle_name") or row.get("model") or "Vehicle",
            "stock": 1,
        })

    return _base_response(
        intent="inventory_analysis",
        metric="stock",
        time_range="current",
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["inventory_table"],
        text_response=f"Current inventory for {display_name} has {len(enriched_rows):,} vehicle record(s) in the DMS database.",
        widget_payloads={"inventory_table": {"rows": enriched_rows, "total_stock": len(enriched_rows), "status_counts": dict(stock_status_counts)}},
    )


def _company_sales_totals(query: str, route: dict[str, Any] | None = None, month_limit: int | None = None) -> tuple[list[str], list[float]]:
    requested: list[str] = []

    if route and isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in requested:
                requested.append(resolved)

    if not requested:
        requested = _smart_company_mentions(query)

    if not requested:
        requested = [row["company_name"] for row in frappe.get_all("DMS Company", fields=["company_name"], order_by="company_name asc")]

    labels = []
    series = []
    for company in requested:
        company_id = _company_id_from_name(company)
        if not company_id:
            continue
        rows = _database_sales_records(company_id, month_limit)
        labels.append(company)
        series.append(sum(float(row.get("final_price") or 0) for row in rows))

    return labels, series


def _build_tenant_comparison_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _is_admin():
        company_id, company_name = _user_company_scope()
        return _base_response(
            intent="unauthorized",
            metric=None,
            time_range=None,
            company_id=company_id,
            company_name=company_name,
            widgets_to_show=[],
            text_response="You do not have permission to access cross-company comparison data.",
            widget_payloads={},
            other={"access_decision": "denied"},
        )

    month_limit = _smart_month_limit(query, route)
    time_text = f"the last {month_limit} months" if month_limit else "all available months"

    labels, series = _company_sales_totals(query, route, month_limit)

    if not labels:
        return _no_data_response("tenant_comparison", "sales", time_text, None, None, f"No cross-company sales data was found in the DMS database over {time_text}.")

    compared_text = ", ".join(labels)
    return _base_response(
        intent="tenant_comparison",
        metric="sales",
        time_range=time_text,
        company_id=None,
        company_name=None,
        widgets_to_show=["tenant_comparison_chart"],
        text_response=f"Company sales comparison for {compared_text} over {time_text} has been prepared from DMS database records.",
        widget_payloads={"tenant_comparison_chart": {"labels": labels, "series": series}},
    )


def _build_all_charts_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    month_limit = _smart_month_limit(query, route) or 6
    company_filter, display_scope = _scope_filters_for_query(query, route)

    company_id = None
    company_name = None
    if "company_id" in company_filter and isinstance(company_filter["company_id"], str):
        company_id = company_filter["company_id"]
        company_name = _company_name_from_id(company_id)

    sales_rows = _database_sales_records(company_id, month_limit)
    service_rows = _database_service_records(company_id, month_limit)

    sales_summary = _aggregate_database_monthly(sales_rows, "final_price", month_limit=month_limit)
    service_summary = _aggregate_database_monthly(service_rows, "name", count_mode=True, month_limit=month_limit)

    widgets = []
    payloads: dict[str, Any] = {}

    widgets.append("sales_chart")
    payloads["sales_chart"] = sales_summary

    widgets.append("service_count_chart")
    payloads["service_count_chart"] = service_summary

    if _is_admin():
        labels, series = _company_sales_totals(query, route, month_limit)
        widgets.append("tenant_comparison_chart")
        payloads["tenant_comparison_chart"] = {"labels": labels, "series": series}

    return _base_response(
        intent="dashboard_charts",
        metric="charts",
        time_range=f"last {month_limit} months",
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=widgets,
        text_response=(
            f"Showing available DMS chart widgets for {display_scope} using the last {month_limit} months of database records. "
            f"Available chart widgets are Sales Chart, Service Count Chart"
            f"{', and Company Comparison Chart' if _is_admin() else ''}."
        ),
        widget_payloads=payloads,
        other={"data_source": "database", "available_widgets": widgets},
    )


def _build_out_of_scope_response() -> dict[str, Any]:
    company_id, company_name = _user_company_scope()
    return _base_response(
        intent="out_of_scope",
        metric=None,
        time_range=None,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=[],
        text_response=(
            "I can assist with DMS dashboard queries including sales, service records, inventory, leads, customers, bookings, "
            "test drives, invoices, vehicles, company comparisons, and available charts."
        ),
        widget_payloads={},
    )



# FINAL_DEMO_AI_PATCH_START

FINAL_RECORD_RESOURCES = {
    "leads": {
        "doctype": "DMS Lead",
        "title": "Leads",
        "keywords": ["lead", "leads", "enquiry", "enquiries", "prospect", "prospects"],
        "search_fields": ["lead_name", "email", "mobile_no", "vehicle_interest", "source", "status"],
        "columns": [
            {"key": "lead_name", "label": "Lead"},
            {"key": "mobile_no", "label": "Mobile"},
            {"key": "vehicle_interest", "label": "Interest"},
            {"key": "source", "label": "Source"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "lead_name", "mobile_no", "email", "vehicle_interest", "source", "status", "creation"],
    },
    "customers": {
        "doctype": "DMS Customer",
        "title": "Customers",
        "keywords": ["customer", "customers", "client", "clients"],
        "search_fields": ["customer_name", "email", "mobile_no", "city", "status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "mobile_no", "label": "Mobile"},
            {"key": "customer_type", "label": "Type"},
            {"key": "total_purchases", "label": "Purchases"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "mobile_no", "email", "customer_type", "total_purchases", "status", "creation"],
    },
    "sales": {
        "doctype": "DMS Vehicle Sale",
        "title": "Vehicle Sales",
        "keywords": ["sale", "sales", "sold", "delivery", "deliveries", "revenue"],
        "search_fields": ["customer_name", "model", "variant", "payment_mode", "status", "invoice_no"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "final_price", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "payment_mode", "status", "invoice_no", "creation"],
    },
    "bookings": {
        "doctype": "DMS Booking",
        "title": "Bookings",
        "keywords": ["booking", "bookings", "reserved", "reservation"],
        "search_fields": ["customer_name", "model", "variant", "status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "booking_amount", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "model", "variant", "booking_amount", "booking_date", "expected_delivery", "status", "creation"],
    },
    "test_drives": {
        "doctype": "DMS Test Drive",
        "title": "Test Drives",
        "keywords": ["test drive", "test drives", "drive", "drives"],
        "search_fields": ["contact_name", "mobile_no", "model", "status"],
        "columns": [
            {"key": "contact_name", "label": "Contact"},
            {"key": "mobile_no", "label": "Mobile"},
            {"key": "model", "label": "Model"},
            {"key": "scheduled_date", "label": "Date"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "contact_name", "mobile_no", "model", "scheduled_date", "scheduled_time", "rating", "status", "creation"],
    },
    "service_jobs": {
        "doctype": "DMS Service Job",
        "title": "Service Jobs",
        "keywords": ["service job", "service jobs", "job card", "job cards", "services", "service"],
        "search_fields": ["customer_name", "vehicle_reg_no", "model", "service_type", "status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "vehicle_reg_no", "label": "Reg No"},
            {"key": "service_type", "label": "Type"},
            {"key": "total_amount", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "vehicle_reg_no", "model", "service_type", "total_amount", "status", "creation"],
    },
    "invoices": {
        "doctype": "DMS Invoice",
        "title": "Invoices",
        "keywords": ["invoice", "invoices", "bill", "bills", "payment", "payments"],
        "search_fields": ["customer_name", "invoice_type", "reference_doc", "payment_status"],
        "columns": [
            {"key": "customer_name", "label": "Customer"},
            {"key": "invoice_type", "label": "Type"},
            {"key": "total_amount", "label": "Total"},
            {"key": "payment_status", "label": "Payment"},
            {"key": "due_date", "label": "Due"},
        ],
        "fields": ["name", "company_id", "company_name", "customer_name", "invoice_type", "total_amount", "payment_status", "due_date", "reference_doc", "creation"],
    },
    "vehicles": {
        "doctype": "DMS Vehicle",
        "title": "Vehicles",
        "keywords": ["vehicle", "vehicles", "inventory", "stock", "cars"],
        "search_fields": ["vehicle_name", "model", "variant", "color", "stock_status", "chassis_no"],
        "columns": [
            {"key": "vehicle_name", "label": "Vehicle"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "color", "label": "Color"},
            {"key": "stock_status", "label": "Status"},
        ],
        "fields": ["name", "company_id", "company_name", "vehicle_name", "model", "variant", "color", "stock_status", "creation"],
    },
}

FINAL_STOPWORDS = {
    "show", "list", "display", "give", "get", "find", "search", "view", "open",
    "the", "a", "an", "of", "for", "to", "me", "all", "latest", "recent",
    "record", "records", "data", "table", "details", "detail", "with", "by",
    "please", "want", "need", "i", "admin", "tenant", "company", "companies",
    "chart", "charts", "graph", "graphs", "dashboard", "relevant", "remaining",
    "more", "next", "rest",
}

FINAL_RESOURCE_WORDS = {
    word
    for config in FINAL_RECORD_RESOURCES.values()
    for keyword in config["keywords"]
    for word in keyword.split()
}


def _final_is_followup_query(query: str) -> bool:
    q = query.lower().strip()
    return any(term in q for term in [
        "i meant", "i mean", "that one", "those", "it", "same", "previous",
        "above", "that data", "that chart", "that table", "remaining", "more",
        "next", "rest",
    ])


def _routing_query(user_query: str, conversation_context: str | None) -> str:
    if conversation_context and _final_is_followup_query(user_query):
        return f"{conversation_context}\nCurrent clarification: {user_query}"
    return user_query


def _final_llm_route(query: str) -> dict[str, Any]:
    if not ENABLE_GEMINI_INTENT:
        return {}

    api_key = os.getenv("GEMINI_API_KEY") or frappe.conf.get("gemini_api_key") or frappe.conf.get("GEMINI_API_KEY")
    if not api_key:
        return {}

    try:
        from google import genai
        from google.genai import types
    except Exception:
        return {}

    prompt = f"""
You are a semantic planner for a Dealer Management System chatbot.

Return only JSON. No markdown.

Possible intents:
- record_lookup
- dashboard_charts
- tenant_comparison
- sales_analysis
- service_analysis
- inventory_analysis
- knowledge_lookup
- out_of_scope

Possible resources:
- leads
- customers
- sales
- bookings
- test_drives
- service_jobs
- invoices
- vehicles

Extract:
- intent
- resource
- companies: array using Honda, NEXA, Jaguar only
- month_limit: integer or null
- search_text: person/customer/model/search phrase or null
- pagination_action: one of first, next, remaining, null
- wants_all_charts: boolean
- confidence: number 0 to 1

Rules:
- "compare sales of honda and nexa" is tenant_comparison, companies ["Honda","NEXA"], not record_lookup.
- "sales for honda and nexa" is tenant_comparison, companies ["Honda","NEXA"], not record_lookup.
- "honda and nexa sales" is tenant_comparison, companies ["Honda","NEXA"], not record_lookup.
- "what was the sales in the last 5 months" is sales_analysis, not record_lookup.
- "nexa sales last 5 months" is sales_analysis, companies ["NEXA"], not record_lookup.
- "show all sales data" is record_lookup, resource sales.
- "show the remaining" means continue the previous record table.
- "invoice for diya kuiren" is record_lookup, resource invoices, search_text "diya kuiren".
- "show invoice of arjun pillai" is record_lookup, resource invoices, search_text "arjun pillai".
- "show all charts we have with last 4 months" is dashboard_charts, wants_all_charts true, month_limit 4.
- If the user asks a chart for one company, include that company only.

User query:
{query}
""".strip()

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "resource": {"type": "string", "nullable": True},
            "companies": {"type": "array", "items": {"type": "string"}},
            "month_limit": {"type": "integer", "nullable": True},
            "search_text": {"type": "string", "nullable": True},
            "pagination_action": {"type": "string", "nullable": True},
            "wants_all_charts": {"type": "boolean"},
            "confidence": {"type": "number"},
        },
        "required": ["intent"],
    }

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return _safe_json_loads(getattr(response, "text", None))
    except Exception:
        return {}


def _final_company_mentions(query: str) -> list[str]:
    found: list[str] = []
    q = query.lower()
    for alias, company in COMPANY_ALIASES.items():
        if not alias or not company:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", q) and company not in found:
            found.append(company)
    order = {"Honda": 0, "NEXA": 1, "Jaguar": 2}
    found.sort(key=lambda value: order.get(value, 99))
    return found


def _final_is_comparison_query(query: str, route: dict[str, Any] | None = None) -> bool:
    if route and route.get("intent") == "tenant_comparison":
        return True
    q = query.lower()
    return any(term in q for term in [
        "compare", "comparison", "versus", " vs ", "against", "between",
        "which company", "which tenant",
    ])


def _final_is_chart_query(query: str, route: dict[str, Any] | None = None) -> bool:
    if route and (route.get("intent") == "dashboard_charts" or route.get("wants_all_charts")):
        return True
    q = query.lower()
    return any(term in q for term in [
        "chart", "charts", "graph", "graphs", "visual", "visualization",
        "widget", "widgets", "trend", "trends", "historical",
        "all charts", "available charts",
    ])


def _final_month_limit(query: str, route: dict[str, Any] | None = None) -> int | None:
    if route and isinstance(route.get("month_limit"), int) and route["month_limit"] > 0:
        return min(route["month_limit"], 24)
    match = re.search(r"last\s+(\d+)\s+months?", query.lower())
    if match:
        return min(int(match.group(1)), 24)
    return _extract_month_limit(query) if "_extract_month_limit" in globals() else None


def _final_month_keys(month_limit: int) -> list[str]:
    today = getdate(nowdate()).replace(day=1)
    return [add_months(today, -(month_limit - index - 1)).strftime("%Y-%m") for index in range(month_limit)]


def _final_metric_summary_intent(query: str, route: dict[str, Any] | None = None) -> str | None:
    # Detect metric-summary questions before record lookup captures sales/service words.
    route_intent = str((route or {}).get("intent") or "")
    if route_intent in {"sales_analysis", "service_analysis", "inventory_analysis"}:
        return route_intent

    q = query.lower().strip()

    record_lookup_terms = [
        "list", "records", "record", "table", "details", "detail", "lookup",
        "show all sales", "show sales records", "show vehicle sales",
    ]

    # Do not override explicit record/table requests.
    if any(term in q for term in record_lookup_terms):
        return None

    summary_terms = [
        "what was", "what is", "how much", "how many", "total", "sum",
        "over the last", "in the last", "last month", "last months",
        "last quarter", "this month", "current month",
    ]

    if any(term in q for term in summary_terms):
        if any(metric in q for metric in ["sales", "revenue", "income"]):
            return "sales_analysis"
        if any(metric in q for metric in ["service count", "service jobs", "services"]):
            return "service_analysis"
        if any(metric in q for metric in ["inventory", "stock"]):
            return "inventory_analysis"

    return None



def _final_route_companies(query: str, route: dict[str, Any] | None = None) -> list[str]:
    """Return tenant/company names detected by Gemini and deterministic aliases."""
    companies: list[str] = []

    if route and isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in companies:
                companies.append(resolved)

    for company in _final_company_mentions(query):
        if company and company not in companies:
            companies.append(company)

    order = {"Honda": 0, "NEXA": 1, "Jaguar": 2}
    companies.sort(key=lambda value: order.get(value, 99))
    return companies


def _final_explicit_record_lookup_query(query: str, route: dict[str, Any] | None = None) -> bool:
    """Return True only when the user clearly asks for rows/details/list/table."""
    q = query.lower().strip()
    route = route or {}

    explicit_terms = [
        "record", "records", "table", "details", "detail", "list", "lookup",
        "find", "search", "show all", "show latest", "view all", "open",
    ]

    explicit_sales_record_phrases = [
        "sales data", "sales records", "vehicle sales records", "vehicle sales data",
        "all sales", "latest sales", "list sales", "show sales data",
        "show all sales data", "show all sales records",
    ]

    if any(term in q for term in explicit_sales_record_phrases):
        return True

    if any(term in q for term in explicit_terms):
        return True

    if re.search(r"\b(invoice|lead|customer|booking|test drive|service job|vehicle)\s+(for|of|named|called)\s+[a-z]", q):
        return True

    if route.get("intent") == "record_lookup":
        if route.get("search_text") and not _final_route_companies(query, route):
            return True
        if any(term in q for term in explicit_terms):
            return True

    return False


def _final_intelligent_intent(query: str, route: dict[str, Any] | None = None) -> str | None:
    """Deterministic guardrail over Gemini/rule routing.

    Gemini is still used when configured, but this guardrail prevents common DMS
    ambiguity where "sales" can mean either KPI analysis or DMS Vehicle Sale rows.
    """
    route = route or {}
    q = query.lower().strip()

    companies = _final_route_companies(query, route)

    has_sales_metric = any(term in q for term in [
        "sales", "revenue", "income", "sale amount", "sales amount", "total sales",
    ])
    has_service_metric = any(term in q for term in [
        "service count", "service jobs", "services", "service revenue", "servicing",
    ])
    has_inventory_metric = any(term in q for term in [
        "inventory", "stock", "available vehicles", "vehicle stock",
    ])

    # Multi-company sales questions are comparisons unless the user explicitly
    # asks for rows/table/list/records.
    if has_sales_metric and len(companies) > 1 and not _final_explicit_record_lookup_query(query, route):
        return "tenant_comparison"

    # Explicit row/table/list requests should remain record lookup.
    if _final_explicit_record_lookup_query(query, route):
        return None

    route_intent = str(route.get("intent") or "")
    if route_intent in {"sales_analysis", "service_analysis", "inventory_analysis", "tenant_comparison"}:
        if route_intent == "tenant_comparison":
            return "tenant_comparison"
        if route_intent == "sales_analysis" and len(companies) > 1:
            return "tenant_comparison"
        return route_intent

    metric_context = any(term in q for term in [
        "what was", "what is", "how much", "how many", "total", "sum",
        "for ", "of ", "in the last", "last ", "this month", "current month",
        "chart", "trend", "graph", "show me",
    ])

    if has_sales_metric:
        if len(companies) > 1 or _final_is_comparison_query(query, route):
            return "tenant_comparison"
        if metric_context or companies:
            return "sales_analysis"
        return "sales_analysis"

    if has_service_metric:
        return "service_analysis"

    if has_inventory_metric:
        return "inventory_analysis"

    return None

def _final_scope_filter(query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    if not _is_admin():
        company_id, company_name = _user_company_scope()
        return ({"company_id": company_id} if company_id else {}, company_name or "your company")

    companies: list[str] = []
    if route and isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in companies:
                companies.append(resolved)

    if not companies:
        companies = _final_company_mentions(query)

    company_ids = [_company_id_from_name(company) for company in companies]
    company_ids = [company_id for company_id in company_ids if company_id]

    if len(company_ids) == 1:
        return {"company_id": company_ids[0]}, companies[0]
    if len(company_ids) > 1:
        return {"company_id": ["in", company_ids]}, " and ".join(companies)
    return {}, "all allowed companies"


def _existing_fields(doctype: str, fields: list[str]) -> list[str]:
    meta = frappe.get_meta(doctype)
    system_fields = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}
    selected = [field for field in fields if field in system_fields or meta.has_field(field)]
    for field in ["name", "creation"]:
        if field not in selected:
            selected.append(field)
    return selected


def _final_detect_record_resource(query: str, route: dict[str, Any] | None = None) -> str | None:
    if _final_is_comparison_query(query, route):
        return None

    if route and route.get("resource") in FINAL_RECORD_RESOURCES:
        return str(route["resource"])

    context = (route or {}).get("_conversation_context") or ""
    combined = f"{query}\n{context}".lower()

    if any(term in query.lower() for term in ["remaining", "more", "next", "rest"]):
        for resource, config in FINAL_RECORD_RESOURCES.items():
            if config["title"].lower() in combined or resource.replace("_", " ") in combined:
                return resource

    for resource, config in FINAL_RECORD_RESOURCES.items():
        if any(keyword in query.lower() for keyword in config["keywords"]):
            return resource

    return None


def _final_extract_search_text(query: str, resource: str, route: dict[str, Any] | None = None) -> str | None:
    if route and route.get("search_text"):
        value = str(route["search_text"]).strip()
        if value:
            return value

    if any(term in query.lower() for term in ["remaining", "more", "next", "rest"]):
        return None

    q = query.lower().strip()
    patterns = [
        r"(?:for|of|named|name|called)\s+([a-z][a-z\s.]+)$",
        r"(?:invoice|lead|customer|booking|sale|service|vehicle)\s+(?:for|of)\s+([a-z][a-z\s.]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate

    words = re.findall(r"[a-zA-Z]+", q)
    cleaned = []
    for word in words:
        normalized = word.lower()
        if normalized in FINAL_STOPWORDS:
            continue
        if normalized in FINAL_RESOURCE_WORDS:
            continue
        if normalized in COMPANY_ALIASES:
            continue
        cleaned.append(word)

    candidate = " ".join(cleaned).strip()
    return candidate if len(candidate) >= 2 else None


def _final_context_offset(query: str, context: str | None) -> int:
    if not context:
        return 0
    if not any(term in query.lower() for term in ["remaining", "more", "next", "rest"]):
        return 0

    patterns = [
        r"Showing\s+(\d+)\s+of\s+(\d+)",
        r"showing\s+(\d+)\s+of\s+(\d+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, context)
        if matches:
            shown, total = matches[-1]
            shown_i = int(shown)
            total_i = int(total)
            return shown_i if shown_i < total_i else 0

    return 0


def _final_row_text(row: dict[str, Any], fields: list[str]) -> str:
    return " ".join(str(row.get(field) or "") for field in fields).lower()


def _final_filter_rows(rows: list[dict[str, Any]], fields: list[str], search_text: str | None) -> list[dict[str, Any]]:
    if not search_text:
        return rows

    needle = search_text.lower().strip()
    if not needle:
        return rows

    exact = [row for row in rows if needle in _final_row_text(row, fields)]
    if exact:
        return exact

    scored = []
    for row in rows:
        best = 0.0
        for field in fields:
            value = str(row.get(field) or "").lower()
            if not value:
                continue
            best = max(best, SequenceMatcher(None, needle, value).ratio())
            for token in needle.split():
                best = max(best, SequenceMatcher(None, token, value).ratio())
        if best >= 0.55:
            scored.append((best, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in scored]


def _record_table_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}
    resource = _final_detect_record_resource(query, route)

    if not resource:
        return _build_out_of_scope_response()

    config = FINAL_RECORD_RESOURCES[resource]
    doctype = config["doctype"]
    fields = _existing_fields(doctype, config["fields"])
    filters, display_scope = _final_scope_filter(query, route)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=500,
    )

    search_text = _final_extract_search_text(query, resource, route)
    rows = _final_filter_rows(rows, config["search_fields"], search_text)

    total_after_filter = len(rows)
    context = route.get("_conversation_context") or ""
    offset = _final_context_offset(query, context)
    page_size = 10
    page_rows = rows[offset:offset + page_size]

    enriched_rows = []
    for row in page_rows:
        item = dict(row)
        item["id"] = item.get("name")
        if item.get("creation"):
            item["created_at"] = str(item.get("creation"))
        if item.get("company_id") and not item.get("company_name"):
            item["company_name"] = _company_name_from_id(item.get("company_id"))
        enriched_rows.append(item)

    shown_to = min(offset + len(enriched_rows), total_after_filter)

    if search_text and total_after_filter == 0:
        message = f"No matching {config['title'].lower()} found for '{search_text}' in {display_scope}."
    elif search_text:
        message = f"Here are the matching {config['title'].lower()} for '{search_text}' in {display_scope}. Showing {shown_to} of {total_after_filter} matched database record(s)."
    elif offset:
        message = f"Here are the remaining {config['title'].lower()} for {display_scope}. Showing {shown_to} of {total_after_filter} database record(s)."
    else:
        message = f"Here are the latest {config['title'].lower()} for {display_scope}. Showing {shown_to} of {total_after_filter} database record(s)."

    company_id, company_name = _resolve_company_scope(query, route)
    return _base_response(
        intent="record_lookup",
        metric=resource,
        time_range="latest records",
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["record_table"],
        text_response=message,
        widget_payloads={
            "record_table": {
                "title": config["title"],
                "resource": resource,
                "doctype": doctype,
                "columns": config["columns"],
                "rows": enriched_rows,
                "total": total_after_filter,
                "shown": shown_to,
                "offset": offset,
                "search_text": search_text,
                "data_source": "database",
            }
        },
        other={"data_source": "database", "doctype": doctype, "search_text": search_text, "offset": offset},
    )


def _final_rows_for_monthly(doctype: str, value_field: str, filters: dict[str, Any], month_limit: int) -> dict[str, Any]:
    labels = _final_month_keys(month_limit)
    totals = {label: 0.0 for label in labels}

    fields = ["creation"]
    if value_field != "count":
        fields.append(value_field)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=_existing_fields(doctype, fields),
        order_by="creation asc",
    )

    for row in rows:
        key = _month_label(row.get("creation"))
        if key not in totals:
            continue
        totals[key] += 1 if value_field == "count" else float(row.get(value_field) or 0)

    series = [totals[label] for label in labels]
    return {"labels": labels, "series": series, "total": sum(series)}


def _final_company_metric(metric: str, query: str, route: dict[str, Any] | None, month_limit: int) -> tuple[list[str], list[float]]:
    companies: list[str] = []

    if route and isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in companies:
                companies.append(resolved)

    if not companies:
        companies = _final_company_mentions(query)

    if not companies:
        companies = [row["company_name"] for row in frappe.get_all("DMS Company", fields=["company_name"], order_by="company_name asc")]

    labels = []
    series = []

    for company in companies:
        company_id = _company_id_from_name(company)
        if not company_id:
            continue

        filters = {"company_id": company_id}
        start, end = _month_window(month_limit)
        if start and end:
            filters["creation"] = ["between", [start, end]]

        if metric == "sales_count":
            value = frappe.db.count("DMS Vehicle Sale", filters) or 0
        else:
            value = frappe.db.get_value("DMS Vehicle Sale", filters, "sum(final_price)") or 0

        labels.append(company)
        series.append(float(value))

    return labels, series


def _build_tenant_comparison_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _is_admin():
        company_id, company_name = _user_company_scope()
        return _base_response(
            intent="unauthorized",
            metric=None,
            time_range=None,
            company_id=company_id,
            company_name=company_name,
            widgets_to_show=[],
            text_response="You do not have permission to access cross-company comparison data.",
            widget_payloads={},
            other={"access_decision": "denied"},
        )

    month_limit = _final_month_limit(query, route)
    time_text = f"the last {month_limit} months" if month_limit else "all available months"
    effective_months = month_limit or 24

    labels, series = _final_company_metric("sales_revenue", query, route, effective_months)

    return _base_response(
        intent="tenant_comparison",
        metric="sales",
        time_range=time_text,
        company_id=None,
        company_name=None,
        widgets_to_show=["tenant_comparison_chart"],
        text_response=f"Company sales comparison for {', '.join(labels)} over {time_text} has been prepared from DMS database records.",
        widget_payloads={"tenant_comparison_chart": {"labels": labels, "series": series}},
    )


def _build_all_charts_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    month_limit = _final_month_limit(query, route) or 6
    filters, display_scope = _final_scope_filter(query, route)

    charts = []

    chart_specs = [
        ("sales_revenue_trend", "Sales revenue trend", "DMS Vehicle Sale", "final_price", "line", "₹"),
        ("sales_count_trend", "Vehicle sales count", "DMS Vehicle Sale", "count", "bar", ""),
        ("service_count_trend", "Service job count", "DMS Service Job", "count", "bar", ""),
        ("service_revenue_trend", "Service revenue trend", "DMS Service Job", "total_amount", "line", "₹"),
        ("lead_count_trend", "Lead count trend", "DMS Lead", "count", "bar", ""),
        ("booking_count_trend", "Booking count trend", "DMS Booking", "count", "bar", ""),
        ("test_drive_count_trend", "Test drive count trend", "DMS Test Drive", "count", "bar", ""),
        ("invoice_amount_trend", "Invoice amount trend", "DMS Invoice", "total_amount", "line", "₹"),
    ]

    for chart_id, title, doctype, field, chart_type, prefix in chart_specs:
        try:
            summary = _final_rows_for_monthly(doctype, field, dict(filters), month_limit)
            charts.append({
                "id": chart_id,
                "title": title,
                "description": f"{title} for {display_scope}",
                "type": chart_type,
                "labels": summary["labels"],
                "series": summary["series"],
                "total": summary["total"],
                "prefix": prefix,
            })
        except Exception:
            continue

    # Inventory stock status chart
    try:
        inv_counts: dict[str, int] = defaultdict(int)
        inv_rows = frappe.get_all(
            "DMS Vehicle",
            filters=filters,
            fields=_existing_fields("DMS Vehicle", ["stock_status"]),
        )
        for row in inv_rows:
            inv_counts[row.get("stock_status") or "Unknown"] += 1
        if inv_counts:
            charts.append({
                "id": "inventory_status",
                "title": "Inventory status",
                "description": f"Vehicle stock status for {display_scope}",
                "type": "bar",
                "labels": list(inv_counts.keys()),
                "series": list(inv_counts.values()),
                "total": sum(inv_counts.values()),
                "prefix": "",
            })
    except Exception:
        pass

    if _is_admin():
        try:
            labels, series = _final_company_metric("sales_revenue", query, route, month_limit)
            charts.append({
                "id": "company_revenue_comparison",
                "title": "Company revenue comparison",
                "description": "Revenue comparison for requested companies",
                "type": "bar",
                "labels": labels,
                "series": series,
                "total": sum(series),
                "prefix": "₹",
            })

            labels2, series2 = _final_company_metric("sales_count", query, route, month_limit)
            charts.append({
                "id": "company_sales_count_comparison",
                "title": "Company sales count comparison",
                "description": "Vehicle sales count comparison for requested companies",
                "type": "bar",
                "labels": labels2,
                "series": series2,
                "total": sum(series2),
                "prefix": "",
            })
        except Exception:
            pass

    company_id, company_name = _resolve_company_scope(query, route)
    return _base_response(
        intent="dashboard_charts",
        metric="charts",
        time_range=f"last {month_limit} months",
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["generic_charts"],
        text_response=f"Showing {len(charts)} available DMS chart(s) for {display_scope} using the last {month_limit} months of database records.",
        widget_payloads={
            "generic_charts": {
                "title": "Available DMS Charts",
                "scope": display_scope,
                "month_limit": month_limit,
                "charts": charts,
                "data_source": "database",
            }
        },
        other={"data_source": "database", "available_chart_count": len(charts)},
    )


def _final_out_of_scope_response() -> dict[str, Any]:
    company_id, company_name = _user_company_scope()
    return _base_response(
        intent="out_of_scope",
        metric=None,
        time_range=None,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=[],
        text_response=(
            "I can assist with DMS dashboard queries including sales, service records, inventory, leads, customers, bookings, "
            "test drives, invoices, vehicles, company comparisons, historical charts, and available widgets."
        ),
        widget_payloads={},
    )

# FINAL_DEMO_AI_PATCH_END

@frappe.whitelist(allow_guest=True)
def query(query: str | None = None):
    payload = _request_json()
    user_query = query or payload.get("query")

    if not user_query or not str(user_query).strip():
        return error("Query is required.", http_status_code=400)

    user_query = str(user_query).strip()
    conversation_context = payload.get("conversation_context") or payload.get("history") or ""
    routing_query = _routing_query(user_query, conversation_context)

    route = _final_llm_route(routing_query)
    route["_conversation_context"] = conversation_context
    metric_summary_intent = _final_metric_summary_intent(routing_query, route)
    intelligent_intent = _final_intelligent_intent(routing_query, route)

    # Security always wins. Gemini is never allowed to authorize data.
    if _should_deny_cross_tenant_request(routing_query):
        data = _build_cross_tenant_denial_response(routing_query)

    # Intelligent metric routing runs before record lookup because "sales" can
    # mean either a KPI/chart or the DMS Vehicle Sale table.
    elif intelligent_intent == "tenant_comparison" or _final_is_comparison_query(routing_query, route):
        data = _build_tenant_comparison_response(routing_query, route)

    # Explicit chart/widget requests use chart builder unless the query is
    # clearly a single metric/tenant analysis handled below.
    elif _final_is_chart_query(routing_query, route) and intelligent_intent is None:
        data = _build_all_charts_response(routing_query, route)

    elif intelligent_intent == "sales_analysis":
        data = _build_sales_response(routing_query, route)

    elif intelligent_intent == "service_analysis":
        data = _build_service_response(routing_query, route)

    elif intelligent_intent == "inventory_analysis":
        data = _build_inventory_response(routing_query, route)

    # Record/table lookup, including fuzzy search and "show remaining".
    elif _final_detect_record_resource(routing_query, route):
        data = _record_table_response(routing_query, route)

    elif _is_knowledge_lookup_query(routing_query) and route.get("intent") not in {"record_lookup", "dashboard_charts"}:
        data = build_knowledge_response(routing_query)

    else:
        intent = route.get("intent") if route.get("intent") in VALID_INTENTS else _detect_intent(routing_query)

        if intent == "sales_analysis":
            data = _build_sales_response(routing_query, route)
        elif intent == "service_analysis":
            data = _build_service_response(routing_query, route)
        elif intent == "inventory_analysis":
            data = _build_inventory_response(routing_query, route)
        elif intent == "tenant_comparison":
            data = _build_tenant_comparison_response(routing_query, route)
        elif intent == "dashboard_charts":
            data = _build_all_charts_response(routing_query, route)
        elif intent == "record_lookup":
            data = _record_table_response(routing_query, route)
        elif intent == "out_of_scope":
            data = _final_out_of_scope_response()
        else:
            data = _final_out_of_scope_response()

    return success(data=data)



@frappe.whitelist(allow_guest=True)
def widget_registry():
    return success(
        data={
            "widgets": [
                {"widget_id": "sales_chart", "title": "Sales Chart", "supported_intents": ["sales_analysis", "dashboard_charts"], "metrics": ["sales"]},
                {"widget_id": "service_count_chart", "title": "Service Count Chart", "supported_intents": ["service_analysis", "dashboard_charts"], "metrics": ["service_count"]},
                {"widget_id": "inventory_table", "title": "Inventory Table", "supported_intents": ["inventory_analysis"], "metrics": ["stock"]},
                {"widget_id": "tenant_comparison_chart", "title": "Company Comparison Chart", "supported_intents": ["tenant_comparison", "dashboard_charts"], "metrics": ["sales"]},
                {"widget_id": "record_table", "title": "Record Table", "supported_intents": ["record_lookup"], "metrics": list(RECORD_RESOURCES.keys())},
            ],
            "widget_ids": ALL_WIDGETS,
            "resources": {key: {"doctype": value["doctype"], "title": value["title"]} for key, value in RECORD_RESOURCES.items()},
        }
    )


@frappe.whitelist(allow_guest=True)
def examples():
    return success(
        data={
            "endpoint": "POST /api/method/dms.api.ai_agent.query",
            "examples": [
                {"query": "What was the sales in the last 5 months?"},
                {"query": "Show service records for the last 3 months"},
                {"query": "What is the current vehicle inventory?"},
                {"query": "Compare sales across Honda and NEXA"},
                {"query": "List the leads"},
                {"query": "Show invoice of Arjun Pillai"},
                {"query": "Show all charts we have with last 4 months of relevant data"},
            ],
            "response_fields": ["intent", "filters_applied", "widgets_to_show", "widgets_to_hide", "text_response", "widget_payloads"],
        }
    )
