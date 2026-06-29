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
    if conversation_context:
        company_followup = _final_company_only_followup_query_v2(user_query, conversation_context)
        if company_followup:
            return company_followup

        if _final_is_followup_query(user_query):
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


# FOLLOWUP_MEMORY_V2_START
def _final_company_only_followup_query_v2(user_query: str, conversation_context: str | None) -> str | None:
    """Rewrite short company-only follow-ups using the latest relevant chat context.

    Example:
      context: sales for honda and nexa over the last 5 months
      query:   for jaguar
      output:  sales for Jaguar over the last 5 months

    This runs before Gemini routing, so Gemini receives a complete query instead
    of a fragment like "for jaguar".
    """
    if not conversation_context:
        return None

    q = user_query.lower().strip()
    q = re.sub(r"[^a-zA-Z\s]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    for prefix in ["what about ", "how about ", "same for ", "show for ", "for ", "about "]:
        if q.startswith(prefix):
            q = q[len(prefix):].strip()

    if not q:
        return None

    words = q.split()
    if len(words) > 6:
        return None

    joiners = {"and", "or", "vs", "versus"}
    company_aliases = {alias for alias, company in COMPANY_ALIASES.items() if company}
    company_words = [word for word in words if word not in joiners]

    if not company_words:
        return None

    if not all(word in company_aliases for word in company_words):
        return None

    companies: list[str] = []
    for word in company_words:
        company = _company_name_from_alias(word)
        if company and company not in companies:
            companies.append(company)

    if not companies:
        return None

    lines = [line.strip() for line in conversation_context.splitlines() if line.strip()]

    latest_relevant = ""
    for line in reversed(lines):
        lower = line.lower()
        if any(term in lower for term in [
            "sales", "revenue", "vehicle sale", "tenant comparison",
            "service", "service job", "inventory", "stock",
            "lead", "invoice", "booking", "test drive",
        ]):
            latest_relevant = lower
            break

    if not latest_relevant:
        latest_relevant = conversation_context.lower()

    if any(term in latest_relevant for term in ["sales", "revenue", "vehicle sale", "tenant comparison"]):
        metric = "sales"
    elif any(term in latest_relevant for term in ["service", "service job", "job card"]):
        metric = "service jobs"
    elif any(term in latest_relevant for term in ["inventory", "stock", "vehicle stock"]):
        metric = "inventory"
    elif any(term in latest_relevant for term in ["lead", "leads"]):
        metric = "leads"
    elif any(term in latest_relevant for term in ["invoice", "invoices"]):
        metric = "invoices"
    elif any(term in latest_relevant for term in ["booking", "bookings"]):
        metric = "bookings"
    elif any(term in latest_relevant for term in ["test drive", "test drives"]):
        metric = "test drives"
    else:
        return None

    # Prefer the latest relevant line for time range, then fall back to full context.
    time_source = latest_relevant
    full_context = conversation_context.lower()

    month_match = re.search(r"last\s+(\d+)\s+months?", time_source) or re.search(r"last\s+(\d+)\s+months?", full_context)
    if month_match:
        time_phrase = f" over the last {month_match.group(1)} months"
    elif "all available months" in time_source:
        time_phrase = " over all available months"
    elif "latest records" in time_source:
        time_phrase = " latest records"
    else:
        time_phrase = ""

    company_text = " and ".join(companies)
    return f"{metric} for {company_text}{time_phrase}".strip()
# FOLLOWUP_MEMORY_V2_END

def _routing_query(user_query: str, conversation_context: str | None) -> str:
    if conversation_context:
        company_followup = _final_company_only_followup_query_v2(user_query, conversation_context)
        if company_followup:
            return company_followup

        if _final_is_followup_query(user_query):
            return f"{conversation_context}\nCurrent clarification: {user_query}"

    return user_query


def _final_llm_route(query: str) -> dict[str, Any]:
    if not ENABLE_GEMINI_INTENT:
        return {
            "_llm_status": "disabled",
            "_llm_error": "ENABLE_GEMINI_INTENT is false",
        }

    api_key = os.getenv("GEMINI_API_KEY") or frappe.conf.get("gemini_api_key") or frappe.conf.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "_llm_status": "missing_api_key",
            "_llm_error": "GEMINI_API_KEY/gemini_api_key not found in environment or site config",
        }

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        return {
            "_llm_status": "import_failed",
            "_llm_error": str(exc)[:500],
        }

    prompt = f"""
You are the PRIMARY semantic planner for a Dealer Management System chatbot.

Return only JSON. No markdown.

The user may ask for:
- KPI summaries
- charts/widgets
- tenant/company comparisons
- table/list/detail lookups
- specific fields like phone number, email, status, vehicle, amount, invoice, tenant/company
- follow-up questions using prior context

The backend will enforce tenant permissions and safely query the database.
You do not authorize access. You only plan the data operation.

Supported intents:
- record_lookup
- dashboard_charts
- tenant_comparison
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

Available companies:
- Honda
- NEXA
- Jaguar

Return these fields:
- intent: one supported intent
- resource: one supported resource or null
- companies: array using Honda, NEXA, Jaguar only
- month_limit: integer or null
- search_text: person/customer/model/invoice/search phrase or null
- requested_fields: array of fields the user wants, such as mobile_no, email, company_name, status, model, final_price, total_amount
- pagination_action: first, next, remaining, or null
- wants_all_charts: boolean
- confidence: number from 0 to 1

Decision rules:
- For every valid DMS question, choose the closest database-backed intent. Do not return out_of_scope for DMS data questions.
- Distinguish sales revenue from vehicle sales count.
- "number of vehicles sold", "how many cars sold", "number of Honda sold", "Honda sold last month", and "number of sales in last 3 months" mean vehicle sales count from DMS Vehicle Sale.
- For vehicle sales count questions, use intent sales_analysis, resource sales, and requested_fields ["count"].
- For "total sales", "sales revenue", "sales amount", "how much sales", and "income", use sales revenue from final_price.
- If the user asks a KPI over multiple months, such as "last 3 months", prefer a chart-capable response by setting month_limit correctly.
- If the user asks a single company question, include that company in companies.
- If the user asks multi-company comparison, use tenant_comparison.
- Tenant permission is not decided by you. The backend enforces authorised scope after your plan.
- Use record_lookup only when the user asks for table/list/records/details OR asks for a specific field about a person/customer/lead/invoice/vehicle.
- "what is the phone number of John Kurien" is record_lookup, resource customers, search_text "John Kurien", requested_fields ["mobile_no", "company_name", "email", "status"].
- "show contact details of John Kurien" is record_lookup, resource customers, search_text "John Kurien", requested_fields ["mobile_no", "email", "company_name", "status"].
- "which tenant customer is John Kurien" is record_lookup, resource customers, search_text "John Kurien", requested_fields ["company_name", "mobile_no", "email", "status"].
- "email of Diya Kuiren" is record_lookup, resource customers, search_text "Diya Kuiren", requested_fields ["email", "mobile_no", "company_name"].
- "invoice for Arjun Pillai" is record_lookup, resource invoices, search_text "Arjun Pillai".
- "show all sales records" is record_lookup, resource sales.
- "sales for honda and nexa" is tenant_comparison, companies ["Honda","NEXA"].
- "sales in last 5 months for honda and nexa" is tenant_comparison, companies ["Honda","NEXA"], month_limit 5.
- "show nexa sales chart for last 5 months" is sales_analysis, companies ["NEXA"], month_limit 5.
- "what was the sales in the last 5 months" is sales_analysis, not record_lookup.
- "show all charts we have with last 4 months" is dashboard_charts, wants_all_charts true, month_limit 4.
- A single-company metric question should become the relevant analysis intent with that company in companies.
- A multi-company sales metric question should become tenant_comparison.
- Do not return out_of_scope for valid DMS data questions.

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
            "requested_fields": {"type": "array", "items": {"type": "string"}},
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

        parsed = _safe_json_loads(getattr(response, "text", None))
        if not isinstance(parsed, dict):
            return {
                "_llm_status": "invalid_response",
                "_llm_error": "Gemini returned non-dict response",
            }

        if parsed.get("intent") not in VALID_INTENTS:
            return {
                "_llm_status": "invalid_intent",
                "_llm_error": f"Invalid intent from Gemini: {parsed.get('intent')}",
                "_raw_route": parsed,
            }

        if not isinstance(parsed.get("companies"), list):
            parsed["companies"] = []

        if not isinstance(parsed.get("requested_fields"), list):
            parsed["requested_fields"] = []

        parsed["_llm_status"] = "ok"
        parsed["_llm_error"] = None
        return parsed

    except Exception as exc:
        return {
            "_llm_status": "call_failed",
            "_llm_error": str(exc)[:500],
        }


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


def _final_contact_like_query(query: str, route: dict[str, Any] | None = None) -> bool:
    q = query.lower()
    if route and route.get("resource") in {"customers", "leads"}:
        return True

    contact_terms = [
        "phone", "mobile", "contact number", "number", "email", "mail",
        "contact details", "details of", "which tenant", "which company",
        "customer is", "lead is",
    ]
    return any(term in q for term in contact_terms)


def _final_requested_fields(query: str, route: dict[str, Any] | None, resource: str) -> list[str]:
    q = query.lower()
    fields: list[str] = []

    route_fields = route.get("requested_fields") if route else None
    if isinstance(route_fields, list):
        for field in route_fields:
            value = str(field).strip()
            if value and value not in fields:
                fields.append(value)

    def add(field: str):
        if field not in fields:
            fields.append(field)

    if any(term in q for term in ["phone", "mobile", "contact number", "number", "call"]):
        add("mobile_no")

    if any(term in q for term in ["email", "mail"]):
        add("email")

    if any(term in q for term in ["tenant", "company", "dealership", "branch"]):
        add("company_name")

    if "status" in q:
        add("status")

    if any(term in q for term in ["vehicle", "model", "car"]):
        add("model")
        add("vehicle_interest")

    if any(term in q for term in ["amount", "price", "sales", "revenue", "invoice total", "total"]):
        add("final_price")
        add("total_amount")

    if any(term in q for term in ["details", "contact details", "everything", "all details"]):
        for field in ["mobile_no", "email", "company_name", "status"]:
            add(field)

    if not fields and resource in {"customers", "leads"}:
        fields = ["mobile_no", "email", "company_name", "status"]

    return fields


def _final_identity_field(resource: str) -> str:
    return {
        "customers": "customer_name",
        "leads": "lead_name",
        "sales": "customer_name",
        "bookings": "customer_name",
        "test_drives": "contact_name",
        "service_jobs": "customer_name",
        "invoices": "customer_name",
        "vehicles": "vehicle_name",
    }.get(resource, "name")


def _final_value(row: dict[str, Any], *fields: str) -> Any:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return value
    return None


def _final_record_detail_text(
    resource: str,
    rows: list[dict[str, Any]],
    query: str,
    route: dict[str, Any] | None,
    search_text: str | None,
    display_scope: str,
    total_after_filter: int,
) -> str | None:
    if not search_text and not _final_contact_like_query(query, route):
        return None

    q = query.lower()
    wants_specific_answer = any(term in q for term in [
        "phone", "mobile", "contact number", "number", "email", "mail",
        "which tenant", "which company", "contact details", "details of",
        "what is", "what's", "tell me",
    ])

    if not wants_specific_answer:
        return None

    if not rows:
        title = FINAL_RECORD_RESOURCES[resource]["title"].lower()
        if search_text:
            return f"No matching {title} found for '{search_text}' in {display_scope}."
        return f"No matching {title} found in {display_scope}."

    requested = _final_requested_fields(query, route, resource)
    identity_field = _final_identity_field(resource)
    title = FINAL_RECORD_RESOURCES[resource]["title"].lower()

    lines = []
    max_rows = min(len(rows), 5)

    if total_after_filter == 1:
        row = rows[0]
        name = _final_value(row, identity_field, "customer_name", "lead_name", "contact_name", "vehicle_name", "name") or "the matching record"
        tenant = _final_value(row, "company_name") or _company_name_from_id(row.get("company_id")) or "Unknown"

        detail_parts = []

        for field in requested:
            if field == "company_name":
                continue

            value = _final_value(row, field)
            if value in (None, ""):
                continue

            label = {
                "mobile_no": "phone number",
                "email": "email",
                "status": "status",
                "model": "model",
                "vehicle_interest": "vehicle interest",
                "final_price": "final price",
                "total_amount": "total amount",
                "customer_type": "customer type",
                "source": "source",
            }.get(field, field.replace("_", " "))

            detail_parts.append(f"{label}: {value}")

        if not detail_parts:
            for field in ["mobile_no", "email", "status", "model", "vehicle_interest", "final_price", "total_amount"]:
                value = _final_value(row, field)
                if value not in (None, ""):
                    detail_parts.append(f"{field.replace('_', ' ')}: {value}")

        details = "; ".join(detail_parts) if detail_parts else "no extra field values were available"
        return f"Found 1 matching {title} for '{search_text or name}' in {display_scope}. {name} belongs to tenant/company {tenant}. Details: {details}."

    lines.append(f"Found {total_after_filter} matching {title} record(s) for '{search_text or query}' in {display_scope}. Showing the best {max_rows}:")
    for index, row in enumerate(rows[:max_rows], start=1):
        name = _final_value(row, identity_field, "customer_name", "lead_name", "contact_name", "vehicle_name", "name") or "Unnamed"
        tenant = _final_value(row, "company_name") or _company_name_from_id(row.get("company_id")) or "Unknown"

        parts = [f"tenant/company: {tenant}"]

        for field in requested:
            if field == "company_name":
                continue
            value = _final_value(row, field)
            if value not in (None, ""):
                parts.append(f"{field.replace('_', ' ')}: {value}")

        lines.append(f"{index}. {name} — " + "; ".join(parts))

    return "\n".join(lines)


def _record_table_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}
    resource = _final_detect_record_resource(query, route)

    if not resource and route.get("resource") in FINAL_RECORD_RESOURCES:
        resource = str(route.get("resource"))

    if not resource and route.get("intent") == "record_lookup" and _final_contact_like_query(query, route):
        resource = "customers"

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

    detail_text = _final_record_detail_text(
        resource=resource,
        rows=enriched_rows,
        query=query,
        route=route,
        search_text=search_text,
        display_scope=display_scope,
        total_after_filter=total_after_filter,
    )

    if detail_text:
        message = detail_text
    elif search_text and total_after_filter == 0:
        message = f"No matching {config['title'].lower()} found for '{search_text}' in {display_scope}."
    elif search_text:
        message = f"Here are the matching {config['title'].lower()} for '{search_text}' in {display_scope}. Showing {shown_to} of {total_after_filter} matched database record(s)."
    elif offset:
        message = f"Here are the remaining {config['title'].lower()} for {display_scope}. Showing {shown_to} of {total_after_filter} database record(s)."
    else:
        message = f"Here are the latest {config['title'].lower()} for {display_scope}. Showing {shown_to} of {total_after_filter} database record(s)."

    columns = list(config["columns"])
    if _is_admin() and not any(column.get("key") == "company_name" for column in columns):
        columns = [{"key": "company_name", "label": "Tenant"}] + columns

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
                "columns": columns,
                "rows": enriched_rows,
                "total": total_after_filter,
                "shown": shown_to,
                "offset": offset,
                "search_text": search_text,
                "requested_fields": _final_requested_fields(query, route, resource),
                "data_source": "database",
            }
        },
        other={
            "data_source": "database",
            "doctype": doctype,
            "search_text": search_text,
            "offset": offset,
            "requested_fields": _final_requested_fields(query, route, resource),
        },
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

    # Mandatory LLM planner.
    # Gemini must decide intent/resource/company/time/search/widgets/fields.
    # There is intentionally no rule-based fallback for normal chat behavior.
    route = _final_llm_route(routing_query)
    route["_conversation_context"] = conversation_context

    llm_status = route.get("_llm_status")
    llm_error = route.get("_llm_error")
    llm_intent = str(route.get("intent") or "").strip()

    if llm_status != "ok" or llm_intent not in VALID_INTENTS:
        data = _base_response(
            intent="backend_llm_error",
            metric=None,
            time_range=None,
            company_id=None,
            company_name=None,
            widgets_to_show=[],
            text_response=(
                "Error encountered due to backend LLM not working. "
                "The chat agent requires Gemini to detect intent, choose widgets, and plan scoped data access."
            ),
            widget_payloads={},
            other={
                "data_source": "none",
                "llm_required": True,
                "llm_enabled": bool(ENABLE_GEMINI_INTENT),
                "llm_status": llm_status or "no_route",
                "llm_error": llm_error,
                "routing_query": routing_query,
            },
        )
        return success(data=data)



    # OPENAI_GPT54MINI_NORMALIZER_START
    # LLM must succeed first. This only normalizes a successful LLM plan
    # into safe backend DMS data execution. If the LLM fails, backend LLM error remains.
    normalized_intent = _openai_gpt54mini_normalized_intent(routing_query, route, llm_intent)
    if normalized_intent in VALID_INTENTS:
        llm_intent = normalized_intent
        route["intent"] = normalized_intent
    # OPENAI_GPT54MINI_NORMALIZER_END

    # Tenant isolation is deterministic and always runs before data access.
    # Admin can access all allowed tenants. Tenant users are restricted to their own company.
    if _should_deny_cross_tenant_request(routing_query):
        data = _build_cross_tenant_denial_response(routing_query)

    elif llm_intent == "tenant_comparison":
        data = _build_tenant_comparison_response(routing_query, route)

    elif llm_intent == "dashboard_charts":
        data = _build_all_charts_response(routing_query, route)

    elif llm_intent == "sales_analysis":
        data = _build_sales_response(routing_query, route)

    elif llm_intent == "service_analysis":
        data = _build_service_response(routing_query, route)

    elif llm_intent == "inventory_analysis":
        data = _build_inventory_response(routing_query, route)

    elif llm_intent == "record_lookup":
        data = _record_table_response(routing_query, route)

    elif llm_intent == "knowledge_lookup":
        data = build_knowledge_response(routing_query)

    elif llm_intent == "out_of_scope":
        data = _final_out_of_scope_response()

    else:
        # This should be unreachable because invalid/missing LLM intent is handled above.
        data = _base_response(
            intent="backend_llm_error",
            metric=None,
            time_range=None,
            company_id=None,
            company_name=None,
            widgets_to_show=[],
            text_response=(
                "Error encountered due to backend LLM not working. "
                "The LLM returned an unsupported routing state."
            ),
            widget_payloads={},
            other={
                "data_source": "none",
                "llm_required": True,
                "llm_enabled": bool(ENABLE_GEMINI_INTENT),
                "llm_status": llm_status or "invalid_state",
                "llm_error": llm_error,
                "llm_intent": llm_intent,
                "routing_query": routing_query,
            },
        )

    # Safe diagnostics for demo/debugging. No secrets.
    try:
        data.setdefault("filters_applied", {}).setdefault("other", {})
        data["filters_applied"]["other"]["llm_required"] = True
        data["filters_applied"]["other"]["llm_intent"] = llm_intent
        data["filters_applied"]["other"]["llm_resource"] = route.get("resource")
        data["filters_applied"]["other"]["llm_companies"] = route.get("companies")
        data["filters_applied"]["other"]["llm_requested_fields"] = route.get("requested_fields")
        data["filters_applied"]["other"]["llm_confidence"] = route.get("confidence")
        data["filters_applied"]["other"]["llm_enabled"] = bool(ENABLE_GEMINI_INTENT)
        data["filters_applied"]["other"]["llm_status"] = llm_status
        data["filters_applied"]["other"]["llm_error"] = llm_error
        data["filters_applied"]["other"]["routing_query"] = routing_query
    except Exception:
        pass

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

# OPENAI_GPT54MINI_FULL_PATCH_START

OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def _openai_gpt54mini_provider_config() -> tuple[str, str | None, str]:
    provider = (
        os.getenv("LLM_PROVIDER")
        or frappe.conf.get("llm_provider")
        or frappe.conf.get("LLM_PROVIDER")
        or "gemini"
    )
    provider = str(provider).strip().lower()

    api_key = (
        os.getenv("OPENAI_API_KEY")
        or frappe.conf.get("openai_api_key")
        or frappe.conf.get("OPENAI_API_KEY")
    )

    model = (
        os.getenv("OPENAI_MODEL")
        or frappe.conf.get("openai_model")
        or frappe.conf.get("OPENAI_MODEL")
        or OPENAI_DEFAULT_MODEL
    )
    model = str(model).strip() or OPENAI_DEFAULT_MODEL

    return provider, api_key, model


def _openai_gpt54mini_planner_prompt(query: str) -> str:
    return f"""
You are Vividity, the semantic planning layer for a Dealer Management System chatbot.

Return only valid JSON matching the provided schema. No markdown. No prose.

Your job:
- Understand the user's natural language question.
- Select the correct DMS intent/resource/company/time/search fields.
- Decide if the answer should be a plain KPI, table/list, chart, or comparison.
- The backend will enforce permissions and query the database. You do not authorize access.

Supported intents:
- record_lookup
- dashboard_charts
- tenant_comparison
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

Available companies:
- Honda
- NEXA
- Jaguar

Return fields:
- intent: one supported intent
- resource: one supported resource or null
- companies: array using Honda, NEXA, Jaguar only
- month_limit: integer or null
- search_text: customer/person/model/invoice/search phrase or null
- requested_fields: array of requested fields, such as count, creation, customer_name, model, final_price, total_amount, mobile_no, email, company_name, status
- pagination_action: first, next, remaining, or null
- wants_all_charts: boolean
- confidence: number from 0 to 1

Core DMS reasoning rules:
1. Valid DMS data questions must not become out_of_scope.
2. Tenant security is handled by backend. You only identify requested company names.
3. "sold", "cars sold", "vehicles sold", "vehicle sales", and "sales records" refer to DMS Vehicle Sale, resource sales.
4. "number of vehicles sold", "how many cars sold", "number of Honda sold", "Honda sold last month", "cars sold this month", and "number of sales in last 3 months" mean sales count, not revenue.
5. For sales count questions, use intent sales_analysis, resource sales, requested_fields ["count"].
6. "total sales", "sales revenue", "sales amount", "how much sales", "income", and "revenue" mean revenue from final_price.
7. "date of Honda cars sold", "when did Honda sell cars", "show sold records", "list cars sold", "who bought Honda cars", and "show sales details" mean record_lookup, resource sales.
8. For sold date/detail questions, requested_fields should include ["creation","customer_name","model","variant","final_price","status"].
9. If the user asks over multiple months, such as "last 3 months", set month_limit to that number.
10. If the question is a KPI over multiple months, it is chart-capable even if the user did not explicitly say "chart".
11. If the user explicitly asks chart/graph/trend/month-wise, route to the analysis intent or dashboard_charts as appropriate.
12. If the user asks "show all charts", "available charts", or "dashboard widgets", use dashboard_charts.
13. If the user asks for table/list/records/details, use record_lookup.
14. If the user asks phone/email/contact/customer field, use record_lookup and the appropriate resource.
15. If the user asks multi-company comparison, use tenant_comparison.
16. Single-company KPI questions should include exactly that company in companies.
17. Do not invent companies outside Honda, NEXA, Jaguar.
18. If the user asks vague DMS data but a resource is clear, choose that resource.

Examples:
- "number of honda sold" -> sales_analysis, resource sales, companies ["Honda"], requested_fields ["count"]
- "honda sold last month" -> sales_analysis, resource sales, companies ["Honda"], requested_fields ["count"]
- "number of sales in last 3 months" -> sales_analysis, resource sales, month_limit 3, requested_fields ["count"]
- "date of honda cars sold" -> record_lookup, resource sales, companies ["Honda"], requested_fields ["creation","customer_name","model","variant","final_price","status"]
- "show honda sold records" -> record_lookup, resource sales, companies ["Honda"]
- "honda sales revenue in last 3 months" -> sales_analysis, resource sales, companies ["Honda"], month_limit 3, requested_fields ["final_price"]
- "show all charts for last 4 months" -> dashboard_charts, wants_all_charts true, month_limit 4
- "how many leads" -> record_lookup, resource leads, requested_fields ["count"]
- "latest bookings" -> record_lookup, resource bookings
- "service jobs last month" -> service_analysis or record_lookup depending whether the user asks count/KPI or list/details
- "invoice amount of Arjun Pillai" -> record_lookup, resource invoices, search_text "Arjun Pillai", requested_fields ["total_amount","payment_status"]
- "what is John Kurien phone number" -> record_lookup, resource customers, search_text "John Kurien", requested_fields ["mobile_no","email","company_name","status"]

User query:
{query}
""".strip()


def _openai_gpt54mini_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "record_lookup",
                    "dashboard_charts",
                    "tenant_comparison",
                    "sales_analysis",
                    "service_analysis",
                    "inventory_analysis",
                    "knowledge_lookup",
                    "out_of_scope",
                ],
            },
            "resource": {
                "anyOf": [
                    {
                        "type": "string",
                        "enum": [
                            "leads",
                            "customers",
                            "sales",
                            "bookings",
                            "test_drives",
                            "service_jobs",
                            "invoices",
                            "vehicles",
                        ],
                    },
                    {"type": "null"},
                ]
            },
            "companies": {
                "type": "array",
                "items": {"type": "string", "enum": ["Honda", "NEXA", "Jaguar"]},
            },
            "month_limit": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "search_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "requested_fields": {"type": "array", "items": {"type": "string"}},
            "pagination_action": {
                "anyOf": [
                    {"type": "string", "enum": ["first", "next", "remaining"]},
                    {"type": "null"},
                ]
            },
            "wants_all_charts": {"type": "boolean"},
            "confidence": {"type": "number"},
        },
        "required": [
            "intent",
            "resource",
            "companies",
            "month_limit",
            "search_text",
            "requested_fields",
            "pagination_action",
            "wants_all_charts",
            "confidence",
        ],
    }


def _openai_gpt54mini_extract_text(response_json: dict[str, Any]) -> str | None:
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]

    pieces: list[str] = []
    for item in response_json.get("output") or []:
        for content in item.get("content") or []:
            if isinstance(content.get("text"), str):
                pieces.append(content["text"])

    if pieces:
        return "\n".join(pieces)

    return None


def _openai_gpt54mini_route(query: str) -> dict[str, Any]:
    _provider, api_key, model = _openai_gpt54mini_provider_config()

    if not api_key:
        return {
            "_llm_status": "missing_api_key",
            "_llm_error": "openai_api_key/OPENAI_API_KEY not found in environment or site config",
            "_llm_provider": "openai",
            "_llm_model": model,
        }

    payload = {
        "model": model,
        "input": _openai_gpt54mini_planner_prompt(query),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "dms_route",
                "strict": True,
                "schema": _openai_gpt54mini_schema(),
            }
        },
        "store": False,
    }

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=75) as res:
            raw = res.read().decode("utf-8")
            response_json = json.loads(raw)

        output_text = _openai_gpt54mini_extract_text(response_json)
        parsed = _safe_json_loads(output_text)

        if not isinstance(parsed, dict):
            return {
                "_llm_status": "invalid_response",
                "_llm_error": "OpenAI returned empty/non-dict structured JSON response",
                "_llm_provider": "openai",
                "_llm_model": model,
            }

        if parsed.get("intent") not in VALID_INTENTS:
            return {
                "_llm_status": "invalid_intent",
                "_llm_error": f"Invalid intent from OpenAI: {parsed.get('intent')}",
                "_raw_route": parsed,
                "_llm_provider": "openai",
                "_llm_model": model,
            }

        if not isinstance(parsed.get("companies"), list):
            parsed["companies"] = []

        if not isinstance(parsed.get("requested_fields"), list):
            parsed["requested_fields"] = []

        parsed["_llm_status"] = "ok"
        parsed["_llm_error"] = None
        parsed["_llm_provider"] = "openai"
        parsed["_llm_model"] = model
        return parsed

    except Exception as exc:
        return {
            "_llm_status": "call_failed",
            "_llm_error": str(exc)[:1000],
            "_llm_provider": "openai",
            "_llm_model": model,
        }


def _openai_gpt54mini_has_any(query: str, terms: list[str]) -> bool:
    q = query.lower()
    return any(term in q for term in terms)


def _openai_gpt54mini_route_companies(query: str, route: dict[str, Any] | None = None) -> list[str]:
    route = route or {}
    companies: list[str] = []

    if isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in companies:
                companies.append(resolved)

    for company in _final_company_mentions(query):
        if company and company not in companies:
            companies.append(company)

    order = {"Honda": 0, "NEXA": 1, "Jaguar": 2}
    companies.sort(key=lambda name: order.get(name, 99))
    return companies


def _openai_gpt54mini_resource_from_query(query: str, route: dict[str, Any] | None = None) -> str | None:
    route = route or {}

    if route.get("resource") in FINAL_RECORD_RESOURCES:
        return str(route["resource"])

    q = query.lower()

    if _openai_gpt54mini_has_any(q, ["sold", "sale", "sales", "vehicle sale", "cars sold", "vehicles sold", "delivery"]):
        return "sales"

    return _final_detect_record_resource(query, route)


def _openai_gpt54mini_time_filter(query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str, int | None]:
    from datetime import timedelta

    q = query.lower().strip()
    today = getdate(nowdate())
    filters: dict[str, Any] = {}

    month_limit = _final_month_limit(query, route)

    if "today" in q:
        d = today.strftime("%Y-%m-%d")
        filters["creation"] = ["between", [d, d]]
        return filters, "today", None

    if "yesterday" in q:
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        filters["creation"] = ["between", [d, d]]
        return filters, "yesterday", None

    if "last month" in q or "previous month" in q:
        first_this_month = today.replace(day=1)
        first_last_month = add_months(first_this_month, -1)
        last_last_month = first_this_month - timedelta(days=1)
        filters["creation"] = [
            "between",
            [first_last_month.strftime("%Y-%m-%d"), last_last_month.strftime("%Y-%m-%d")],
        ]
        return filters, "last month", 1

    if "this month" in q or "current month" in q:
        first_this_month = today.replace(day=1)
        filters["creation"] = [
            "between",
            [first_this_month.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")],
        ]
        return filters, "this month", 1

    if "last week" in q or "past week" in q:
        start = today - timedelta(days=7)
        filters["creation"] = ["between", [start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")]]
        return filters, "the last 7 days", None

    if month_limit:
        start, end = _month_window(month_limit)
        if start and end:
            filters["creation"] = ["between", [start, end]]
        return filters, f"the last {month_limit} months", month_limit

    return filters, "all available months", None


def _openai_gpt54mini_sales_count_query(query: str, route: dict[str, Any] | None = None) -> bool:
    q = query.lower().strip()
    route = route or {}

    if _openai_gpt54mini_has_any(q, ["phone number", "contact number", "mobile number", "email of", "mail of"]):
        return False

    if _openai_gpt54mini_has_any(q, [
        "revenue", "income", "sales amount", "sale amount", "sales value",
        "total sales", "how much sales", "how much revenue",
    ]):
        return False

    requested_fields = route.get("requested_fields")
    if isinstance(requested_fields, list):
        joined = " ".join(str(field).lower() for field in requested_fields)
        if "count" in joined and _openai_gpt54mini_has_any(q, ["sold", "sale", "sales", "vehicle", "vehicles", "car", "cars"]):
            return True

    if _openai_gpt54mini_has_any(q, ["how many", "number of", "count of", "total number", "sales count"]):
        if _openai_gpt54mini_has_any(q, ["sold", "sale", "sales", "vehicle", "vehicles", "car", "cars", "honda", "nexa", "jaguar"]):
            return True

    if _openai_gpt54mini_has_any(q, ["sold", "cars sold", "vehicles sold", "units sold", "sold cars", "sold vehicles"]):
        return True

    return False


def _openai_gpt54mini_revenue_query(query: str) -> bool:
    return _openai_gpt54mini_has_any(query, [
        "revenue", "income", "sales amount", "sale amount", "sales value",
        "total sales", "how much sales", "how much revenue",
    ])


def _openai_gpt54mini_detail_or_date_query(query: str) -> bool:
    return _openai_gpt54mini_has_any(query, [
        "date", "dates", "when", "which date", "sale date", "sold date",
        "details", "detail", "list", "records", "record", "show", "latest",
        "who", "which customer", "customer name", "invoice", "status",
    ])


def _openai_gpt54mini_should_chart(query: str, route: dict[str, Any] | None = None, month_limit: int | None = None) -> bool:
    q = query.lower().strip()

    if _final_is_chart_query(query, route):
        return True

    if month_limit and month_limit >= 2:
        return True

    if re.search(r"last\s+\d+\s+months?", q):
        return True

    if _openai_gpt54mini_has_any(q, ["monthly", "month wise", "month-wise", "trend", "over time"]):
        return True

    return False


def _openai_gpt54mini_normalized_intent(query: str, route: dict[str, Any] | None, current_intent: str) -> str | None:
    route = route or {}
    q = query.lower().strip()

    if _final_is_chart_query(query, route) and _openai_gpt54mini_has_any(q, ["all chart", "available chart", "widgets"]):
        return "dashboard_charts"

    resource = _openai_gpt54mini_resource_from_query(query, route)
    companies = _openai_gpt54mini_route_companies(query, route)

    if resource == "sales":
        if len(companies) > 1 or _final_is_comparison_query(query, route):
            return "tenant_comparison"

        if _openai_gpt54mini_detail_or_date_query(query):
            return "record_lookup"

        return "sales_analysis"

    if resource:
        return "record_lookup"

    if current_intent in VALID_INTENTS:
        return current_intent

    return None


def _openai_gpt54mini_scope(query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str, str | None, str | None]:
    filters, display_scope = _final_scope_filter(query, route)
    company_id, company_name = _resolve_company_scope(query, route)
    return filters, display_scope, company_id, company_name


def _openai_gpt54mini_apply_period(filters: dict[str, Any], query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str, int | None]:
    time_filter, time_text, month_limit = _openai_gpt54mini_time_filter(query, route)
    final_filters = dict(filters)
    final_filters.update(time_filter)
    return final_filters, time_text, month_limit


def _openai_gpt54mini_monthly_summary(rows: list[dict[str, Any]], value_field: str, count_mode: bool = False, month_limit: int | None = None) -> dict[str, Any]:
    labels = _final_month_keys(month_limit) if month_limit and month_limit >= 2 else []
    totals: dict[str, float] = defaultdict(float)

    for label in labels:
        totals[label] = 0.0

    for row in rows:
        label = _month_label(row.get("creation")) or "Unknown"
        if labels and label not in totals:
            continue
        totals[label] += 1 if count_mode else float(row.get(value_field) or 0)

    final_labels = labels if labels else sorted(totals.keys())
    series = [totals[label] for label in final_labels]
    total = sum(series)

    highest_month = None
    if final_labels:
        peak_index = max(range(len(final_labels)), key=lambda index: series[index])
        highest_month = {"month": final_labels[peak_index], value_field: series[peak_index]}

    return {
        "labels": final_labels,
        "series": series,
        "total": total,
        "highest_month": highest_month,
    }


def _openai_gpt54mini_resource_fields(resource: str) -> list[str]:
    base = FINAL_RECORD_RESOURCES[resource]["fields"]
    extras = ["company_name", "creation"]

    if resource == "sales":
        extras += ["customer_name", "model", "variant", "final_price", "payment_mode", "status", "invoice_no"]
    elif resource == "invoices":
        extras += ["customer_name", "invoice_type", "total_amount", "payment_status", "due_date", "reference_doc"]
    elif resource == "service_jobs":
        extras += ["customer_name", "vehicle_reg_no", "model", "service_type", "total_amount", "status"]
    elif resource == "bookings":
        extras += ["customer_name", "model", "variant", "booking_amount", "booking_date", "expected_delivery", "status"]
    elif resource == "test_drives":
        extras += ["contact_name", "mobile_no", "model", "scheduled_date", "scheduled_time", "status"]
    elif resource == "vehicles":
        extras += ["vehicle_name", "model", "variant", "color", "stock_status"]
    elif resource == "customers":
        extras += ["customer_name", "mobile_no", "email", "customer_type", "total_purchases", "status"]
    elif resource == "leads":
        extras += ["lead_name", "mobile_no", "email", "vehicle_interest", "source", "status"]

    merged = []
    for field in base + extras:
        if field not in merged:
            merged.append(field)
    return merged


def _openai_gpt54mini_columns(resource: str) -> list[dict[str, str]]:
    if resource == "sales":
        columns = [
            {"key": "sale_date", "label": "Sale Date"},
            {"key": "company_name", "label": "Tenant"},
            {"key": "customer_name", "label": "Customer"},
            {"key": "model", "label": "Model"},
            {"key": "variant", "label": "Variant"},
            {"key": "final_price", "label": "Amount"},
            {"key": "status", "label": "Status"},
        ]
    else:
        columns = list(FINAL_RECORD_RESOURCES[resource]["columns"])
        if _is_admin() and not any(column.get("key") == "company_name" for column in columns):
            columns = [{"key": "company_name", "label": "Tenant"}] + columns

    if not _is_admin():
        columns = [column for column in columns if column.get("key") != "company_name"]

    return columns


def _openai_gpt54mini_enrich_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["id"] = item.get("name")
    if item.get("creation"):
        item["created_at"] = str(item.get("creation"))
        item["sale_date"] = str(item.get("creation"))[:10]
    if item.get("company_id") and not item.get("company_name"):
        item["company_name"] = _company_name_from_id(item.get("company_id"))
    return item


def _openai_gpt54mini_row_summary(resource: str, row: dict[str, Any]) -> str:
    if resource == "sales":
        sale_date = row.get("sale_date") or str(row.get("creation") or "")[:10] or "Unknown date"
        customer = row.get("customer_name") or "Unknown customer"
        model = row.get("model") or "Unknown model"
        amount = row.get("final_price")
        amount_text = f"₹{float(amount):,.0f}" if amount not in (None, "") else "amount not available"
        status = row.get("status") or ""
        status_text = f" — {status}" if status else ""
        return f"{sale_date} — {customer} — {model} — {amount_text}{status_text}"

    identity = _final_identity_field(resource)
    name = _final_value(row, identity, "customer_name", "lead_name", "contact_name", "vehicle_name", "name") or "Unnamed"
    created = str(row.get("creation") or "")[:10]
    status = row.get("status") or row.get("payment_status") or row.get("stock_status")
    parts = [str(name)]
    if created:
        parts.append(f"date: {created}")
    if status:
        parts.append(f"status: {status}")
    return " — ".join(parts)


def _openai_gpt54mini_count_query(query: str, resource: str, route: dict[str, Any] | None = None) -> bool:
    q = query.lower()

    if resource == "sales":
        return _openai_gpt54mini_sales_count_query(query, route)

    return _openai_gpt54mini_has_any(q, ["how many", "number of", "count of", "total number", "total count"])


def _record_table_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}
    resource = _openai_gpt54mini_resource_from_query(query, route)

    if not resource and route.get("resource") in FINAL_RECORD_RESOURCES:
        resource = str(route["resource"])

    if not resource and route.get("intent") == "record_lookup" and _final_contact_like_query(query, route):
        resource = "customers"

    if not resource or resource not in FINAL_RECORD_RESOURCES:
        return _final_out_of_scope_response()

    config = FINAL_RECORD_RESOURCES[resource]
    doctype = config["doctype"]

    base_filters, display_scope, company_id, company_name = _openai_gpt54mini_scope(query, route)
    filters, time_text, _month_limit = _openai_gpt54mini_apply_period(base_filters, query, route)

    if resource == "sales":
        filters["status"] = ["!=", "Cancelled"]

    fields = _existing_fields(doctype, _openai_gpt54mini_resource_fields(resource))

    if _openai_gpt54mini_count_query(query, resource, route) and not _openai_gpt54mini_detail_or_date_query(query):
        try:
            count_value = frappe.db.count(doctype, filters) or 0
        except Exception:
            count_value = 0

        if resource == "sales":
            text = f"{display_scope} sold {count_value:,.0f} vehicle(s) over {time_text}."
        else:
            text = f"There are {count_value:,.0f} {config['title'].lower()} record(s) for {display_scope} over {time_text}."

        return _base_response(
            intent="record_lookup",
            metric=f"{resource}_count",
            time_range=time_text,
            company_id=company_id,
            company_name=company_name,
            widgets_to_show=[],
            text_response=text,
            widget_payloads={},
            other={"data_source": "database", "doctype": doctype, "answer_type": "record_count"},
        )

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=500,
    )

    search_text = _final_extract_search_text(query, resource, route)
    if search_text:
        rows = _final_filter_rows(rows, config["search_fields"], search_text)

    total_after_filter = len(rows)
    context = route.get("_conversation_context") or ""
    offset = _final_context_offset(query, context)
    page_size = 10
    page_rows = rows[offset:offset + page_size]

    enriched_rows = [_openai_gpt54mini_enrich_row(row) for row in page_rows]
    shown_to = min(offset + len(enriched_rows), total_after_filter)

    detail_text = _final_record_detail_text(
        resource=resource,
        rows=enriched_rows,
        query=query,
        route=route,
        search_text=search_text,
        display_scope=display_scope,
        total_after_filter=total_after_filter,
    )

    if detail_text:
        message = detail_text
    elif total_after_filter == 0:
        if search_text:
            message = f"No matching {config['title'].lower()} found for '{search_text}' in {display_scope} over {time_text}."
        else:
            message = f"No {config['title'].lower()} records found for {display_scope} over {time_text}."
    elif _openai_gpt54mini_detail_or_date_query(query):
        lines = [f"Here are the {config['title'].lower()} record(s) for {display_scope} over {time_text}. Showing {shown_to} of {total_after_filter}:"]
        for idx, row in enumerate(enriched_rows[:5], start=1):
            lines.append(f"{idx}. {_openai_gpt54mini_row_summary(resource, row)}")
        message = "\n".join(lines)
    elif search_text:
        message = f"Here are the matching {config['title'].lower()} for '{search_text}' in {display_scope}. Showing {shown_to} of {total_after_filter} matched database record(s)."
    elif offset:
        message = f"Here are the remaining {config['title'].lower()} for {display_scope}. Showing {shown_to} of {total_after_filter} database record(s)."
    else:
        message = f"Here are the latest {config['title'].lower()} for {display_scope}. Showing {shown_to} of {total_after_filter} database record(s)."

    return _base_response(
        intent="record_lookup",
        metric=resource,
        time_range=time_text,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=["record_table"],
        text_response=message,
        widget_payloads={
            "record_table": {
                "title": config["title"] if resource != "sales" else "Vehicle Sales",
                "resource": resource,
                "doctype": doctype,
                "columns": _openai_gpt54mini_columns(resource),
                "rows": enriched_rows,
                "total": total_after_filter,
                "shown": shown_to,
                "offset": offset,
                "search_text": search_text,
                "requested_fields": _final_requested_fields(query, route, resource),
                "data_source": "database",
            }
        },
        other={
            "data_source": "database",
            "doctype": doctype,
            "search_text": search_text,
            "offset": offset,
            "requested_fields": _final_requested_fields(query, route, resource),
            "answer_type": "generic_record_lookup",
        },
    )


def _build_sales_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}
    company_id, company_name = _resolve_company_scope(query, route)
    display_name = company_name or "all allowed companies"

    base_filters: dict[str, Any] = {"status": ["!=", "Cancelled"]}
    if company_id:
        base_filters["company_id"] = company_id

    filters, time_text, month_limit = _openai_gpt54mini_apply_period(base_filters, query, route)

    rows = frappe.get_all(
        "DMS Vehicle Sale",
        filters=filters,
        fields=_existing_fields(
            "DMS Vehicle Sale",
            ["name", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "status", "creation"],
        ),
        order_by="creation asc",
    )

    is_count = _openai_gpt54mini_sales_count_query(query, route)
    chart_needed = _openai_gpt54mini_should_chart(query, route, month_limit)

    if not rows:
        return _no_data_response(
            "sales_analysis",
            "sales_count" if is_count else "sales",
            time_text,
            company_id,
            company_name,
            f"No vehicle sales data was found in the DMS database for {display_name} over {time_text}.",
        )

    if is_count:
        summary = _openai_gpt54mini_monthly_summary(rows, "name", count_mode=True, month_limit=month_limit)
        total_count = int(summary["total"])

        if company_name:
            text_response = f"{company_name} sold {total_count:,} vehicle(s) over {time_text}."
        else:
            text_response = f"Total vehicles sold for {display_name} over {time_text} were {total_count:,}."

        widgets_to_show: list[str] = []
        widget_payloads: dict[str, Any] = {}

        if chart_needed:
            widgets_to_show = ["generic_charts"]
            widget_payloads["generic_charts"] = {
                "title": "Vehicle Sales Count",
                "scope": display_name,
                "month_limit": month_limit or len(summary["labels"]),
                "charts": [{
                    "id": "vehicle_sales_count",
                    "title": "Vehicle sales count",
                    "description": f"Vehicle sales count for {display_name}",
                    "type": "bar",
                    "labels": summary["labels"],
                    "series": summary["series"],
                    "total": summary["total"],
                    "prefix": "",
                }],
                "data_source": "database",
            }

        return _base_response(
            intent="sales_analysis",
            metric="sales_count",
            time_range=time_text,
            company_id=company_id,
            company_name=company_name,
            widgets_to_show=widgets_to_show,
            text_response=text_response,
            widget_payloads=widget_payloads,
            other={"data_source": "database", "answer_type": "vehicle_sales_count"},
        )

    summary = _openai_gpt54mini_monthly_summary(rows, "final_price", count_mode=False, month_limit=month_limit)
    highest = summary.get("highest_month")
    highest_month = {"month": highest["month"], "sales": highest["final_price"]} if highest else None

    text_response = f"Total sales for {display_name} over {time_text} were ₹{summary['total']:,.0f}."
    if highest_month:
        text_response += f" The highest month was {highest_month['month']} with ₹{highest_month['sales']:,.0f}."

    widgets_to_show: list[str] = []
    widget_payloads: dict[str, Any] = {}

    if chart_needed:
        widgets_to_show = ["sales_chart"]
        widget_payloads["sales_chart"] = {
            "labels": summary["labels"],
            "series": summary["series"],
            "total": summary["total"],
            "highest_month": highest_month,
        }

    return _base_response(
        intent="sales_analysis",
        metric="sales",
        time_range=time_text,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=widgets_to_show,
        text_response=text_response,
        widget_payloads=widget_payloads,
        other={"data_source": "database", "answer_type": "sales_revenue"},
    )


def _openai_gpt54mini_company_values(query: str, route: dict[str, Any] | None, metric: str) -> tuple[list[str], list[float], str]:
    route = route or {}
    time_filter, time_text, _month_limit = _openai_gpt54mini_time_filter(query, route)

    companies = _openai_gpt54mini_route_companies(query, route)
    if not companies:
        companies = [row["company_name"] for row in frappe.get_all("DMS Company", fields=["company_name"], order_by="company_name asc")]

    labels: list[str] = []
    series: list[float] = []

    for company in companies:
        company_id = _company_id_from_name(company)
        if not company_id:
            continue

        filters: dict[str, Any] = {"company_id": company_id, "status": ["!=", "Cancelled"]}
        filters.update(time_filter)

        if metric == "sales_count":
            value = frappe.db.count("DMS Vehicle Sale", filters) or 0
        else:
            value = frappe.db.get_value("DMS Vehicle Sale", filters, "sum(final_price)") or 0

        labels.append(company)
        series.append(float(value))

    return labels, series, time_text


def _build_tenant_comparison_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}

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

    is_count = _openai_gpt54mini_sales_count_query(query, route)
    metric = "sales_count" if is_count else "sales_revenue"

    labels, series, time_text = _openai_gpt54mini_company_values(query, route, metric)
    chart_needed = _final_is_chart_query(query, route) or _final_is_comparison_query(query, route) or len(labels) > 1

    if is_count:
        parts = [f"{label}: {int(value):,} vehicle(s)" for label, value in zip(labels, series)]
        text_response = f"Vehicle sales count over {time_text}: " + "; ".join(parts) + "."
        response_metric = "sales_count"
    else:
        parts = [f"{label}: ₹{value:,.0f}" for label, value in zip(labels, series)]
        text_response = f"Sales comparison over {time_text}: " + "; ".join(parts) + "."
        response_metric = "sales"

    widgets_to_show: list[str] = []
    widget_payloads: dict[str, Any] = {}

    if chart_needed:
        widgets_to_show = ["tenant_comparison_chart"]
        widget_payloads["tenant_comparison_chart"] = {
            "labels": labels,
            "series": series,
        }

    return _base_response(
        intent="tenant_comparison",
        metric=response_metric,
        time_range=time_text,
        company_id=None,
        company_name=None,
        widgets_to_show=widgets_to_show,
        text_response=text_response,
        widget_payloads=widget_payloads,
        other={"data_source": "database", "answer_type": response_metric},
    )


def _final_llm_route(query: str) -> dict[str, Any]:
    provider, _openai_key, _openai_model = _openai_gpt54mini_provider_config()

    if provider == "openai":
        return _openai_gpt54mini_route(query)

    # Gemini remains available as fallback provider only if llm_provider is set back to gemini.
    if not ENABLE_GEMINI_INTENT:
        return {
            "_llm_status": "disabled",
            "_llm_error": "ENABLE_GEMINI_INTENT is false",
        }

    api_key = os.getenv("GEMINI_API_KEY") or frappe.conf.get("gemini_api_key") or frappe.conf.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "_llm_status": "missing_api_key",
            "_llm_error": "GEMINI_API_KEY/gemini_api_key not found in environment or site config",
        }

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        return {
            "_llm_status": "import_failed",
            "_llm_error": str(exc)[:500],
        }

    prompt = _openai_gpt54mini_planner_prompt(query)

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "resource": {"type": "string", "nullable": True},
            "companies": {"type": "array", "items": {"type": "string"}},
            "month_limit": {"type": "integer", "nullable": True},
            "search_text": {"type": "string", "nullable": True},
            "requested_fields": {"type": "array", "items": {"type": "string"}},
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

        parsed = _safe_json_loads(getattr(response, "text", None))
        if not isinstance(parsed, dict):
            return {
                "_llm_status": "invalid_response",
                "_llm_error": "Gemini returned non-dict response",
            }

        if parsed.get("intent") not in VALID_INTENTS:
            return {
                "_llm_status": "invalid_intent",
                "_llm_error": f"Invalid intent from Gemini: {parsed.get('intent')}",
                "_raw_route": parsed,
            }

        if not isinstance(parsed.get("companies"), list):
            parsed["companies"] = []

        if not isinstance(parsed.get("requested_fields"), list):
            parsed["requested_fields"] = []

        parsed["_llm_status"] = "ok"
        parsed["_llm_error"] = None
        parsed["_llm_provider"] = "gemini"
        parsed["_llm_model"] = GEMINI_MODEL
        return parsed

    except Exception as exc:
        return {
            "_llm_status": "call_failed",
            "_llm_error": str(exc)[:500],
            "_llm_provider": "gemini",
            "_llm_model": GEMINI_MODEL,
        }

# OPENAI_GPT54MINI_FULL_PATCH_END

# OPENAI_INTELLIGENCE_V2_PATCH_START

def _openai_intel_number_word(value: str | None) -> int | None:
    if not value:
        return None

    value = str(value).strip().lower()
    mapping = {
        "one": 1,
        "two": 2,
        "couple": 2,
        "three": 3,
        "few": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "several": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }

    if value.isdigit():
        return int(value)

    return mapping.get(value)


def _openai_intel_context_text(route: dict[str, Any] | None = None) -> str:
    route = route or {}
    context = (
        route.get("_conversation_context")
        or route.get("conversation_context")
        or route.get("context")
        or ""
    )
    return str(context or "")


def _openai_intel_is_short_followup(query: str) -> bool:
    q = query.lower().strip()
    words = re.findall(r"[a-zA-Z0-9]+", q)

    if len(words) <= 6 and any(term in q for term in [
        "last", "past", "this", "previous", "month", "months",
        "week", "weeks", "year", "years", "then", "that", "those",
    ]):
        return True

    if q in {
        "in last 3 months", "in last 3 months?", "last 3 months",
        "last few months", "few months", "last month", "this month",
        "what about last month", "what about this month",
    }:
        return True

    return False


def _openai_intel_effective_query(query: str, route: dict[str, Any] | None = None) -> str:
    context = _openai_intel_context_text(route)
    q = str(query or "").strip()

    if not context:
        return q

    resource_words = [
        "sale", "sales", "sold", "revenue", "lead", "leads", "customer",
        "customers", "booking", "bookings", "test drive", "service",
        "invoice", "vehicle", "inventory", "honda", "nexa", "jaguar",
    ]

    q_lower = q.lower()
    has_resource = any(word in q_lower for word in resource_words)

    if _openai_intel_is_short_followup(q) or not has_resource:
        return context[-2500:] + "\nCurrent user follow-up: " + q

    return q


def _openai_intel_month_limit(query: str, route: dict[str, Any] | None = None) -> int | None:
    current = str(query or "").lower()
    effective = _openai_intel_effective_query(query, route).lower()

    # Prioritize the current user message first.
    for q in [current, effective]:
        m = re.search(
            r"(?:last|past|previous)\s+(\d+|one|two|couple|three|few|four|five|six|several|seven|eight|nine|ten|eleven|twelve)\s+months?",
            q,
        )
        if m:
            value = _openai_intel_number_word(m.group(1))
            if value:
                return value

        if "last few months" in q or "past few months" in q or "recent few months" in q:
            return 3

        if "last couple months" in q or "past couple months" in q:
            return 2

        if "last several months" in q or "past several months" in q:
            return 6

    try:
        return _final_month_limit(query, route)
    except Exception:
        return None


def _openai_gpt54mini_time_filter(query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str, int | None]:
    from datetime import timedelta

    current = str(query or "").lower().strip()
    effective = _openai_intel_effective_query(query, route).lower().strip()
    today = getdate(nowdate())
    filters: dict[str, Any] = {}

    # Current query has priority for date override.
    for q in [current, effective]:
        if "today" in q:
            d = today.strftime("%Y-%m-%d")
            filters["creation"] = ["between", [d, d]]
            return filters, "today", None

        if "yesterday" in q:
            d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            filters["creation"] = ["between", [d, d]]
            return filters, "yesterday", None

        if "last month" in q or "previous month" in q:
            first_this_month = today.replace(day=1)
            first_last_month = add_months(first_this_month, -1)
            last_last_month = first_this_month - timedelta(days=1)
            filters["creation"] = [
                "between",
                [first_last_month.strftime("%Y-%m-%d"), last_last_month.strftime("%Y-%m-%d")],
            ]
            return filters, "last month", 1

        if "this month" in q or "current month" in q:
            first_this_month = today.replace(day=1)
            filters["creation"] = [
                "between",
                [first_this_month.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")],
            ]
            return filters, "this month", 1

        if "last week" in q or "past week" in q:
            start = today - timedelta(days=7)
            filters["creation"] = ["between", [start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")]]
            return filters, "the last 7 days", None

    month_limit = _openai_intel_month_limit(query, route)
    if month_limit:
        start, end = _month_window(month_limit)
        if start and end:
            filters["creation"] = ["between", [start, end]]
        return filters, f"the last {month_limit} months", month_limit

    return filters, "all available months", None


def _openai_gpt54mini_resource_from_query(query: str, route: dict[str, Any] | None = None) -> str | None:
    route = route or {}

    if route.get("resource") in FINAL_RECORD_RESOURCES:
        return str(route["resource"])

    effective = _openai_intel_effective_query(query, route)
    q = effective.lower()

    if any(term in q for term in [
        "sold", "sale", "sales", "vehicle sale", "cars sold",
        "vehicles sold", "units sold", "delivery", "revenue", "income",
    ]):
        return "sales"

    detected = _final_detect_record_resource(effective, route)
    if detected:
        return detected

    return _final_detect_record_resource(query, route)


def _openai_gpt54mini_route_companies(query: str, route: dict[str, Any] | None = None) -> list[str]:
    route = route or {}
    effective = _openai_intel_effective_query(query, route)
    companies: list[str] = []

    if isinstance(route.get("companies"), list):
        for company in route["companies"]:
            resolved = _company_name_from_alias(str(company))
            if resolved and resolved not in companies:
                companies.append(resolved)

    for company in _final_company_mentions(effective):
        if company and company not in companies:
            companies.append(company)

    order = {"Honda": 0, "NEXA": 1, "Jaguar": 2}
    companies.sort(key=lambda name: order.get(name, 99))
    return companies


def _openai_gpt54mini_sales_count_query(query: str, route: dict[str, Any] | None = None) -> bool:
    route = route or {}
    effective = _openai_intel_effective_query(query, route).lower().strip()
    current = str(query or "").lower().strip()

    combined = effective

    if any(term in combined for term in [
        "phone number", "contact number", "mobile number", "email of", "mail of"
    ]):
        return False

    if any(term in combined for term in [
        "revenue", "income", "sales amount", "sale amount", "sales value",
        "total sales amount", "how much revenue", "how much sales amount",
    ]):
        return False

    requested_fields = route.get("requested_fields")
    if isinstance(requested_fields, list):
        joined = " ".join(str(field).lower() for field in requested_fields)
        if "count" in joined:
            return True

    # In this DMS demo, plain "sales" around vehicles means unit count unless revenue/amount is explicit.
    sales_words = [
        "sold", "cars sold", "vehicles sold", "units sold", "sold cars",
        "sold vehicles", "sales for", "sale count", "sales count",
        "number of sales", "how many sales", "number of honda", "number of nexa",
        "number of jaguar",
    ]

    count_words = ["how many", "number of", "count of", "total number", "count"]

    if any(term in combined for term in count_words) and any(term in combined for term in [
        "sale", "sales", "sold", "vehicle", "vehicles", "car", "cars", "honda", "nexa", "jaguar"
    ]):
        return True

    if any(term in combined for term in sales_words):
        return True

    # Short follow-up like "in last 3 months?" after a sales-count question.
    if _openai_intel_is_short_followup(current) and any(term in combined for term in ["sales", "sold", "vehicles sold", "cars sold"]):
        return True

    return False


def _openai_gpt54mini_revenue_query(query: str) -> bool:
    q = str(query or "").lower()
    return any(term in q for term in [
        "revenue", "income", "sales amount", "sale amount", "sales value",
        "total sales amount", "how much revenue", "how much sales amount",
    ])


def _openai_gpt54mini_detail_or_date_query(query: str) -> bool:
    q = str(query or "").lower()
    return any(term in q for term in [
        "date", "dates", "when", "which date", "sale date", "sold date",
        "details", "detail", "list", "records", "record", "show", "latest",
        "who", "which customer", "customer name", "invoice", "status",
    ])


def _openai_gpt54mini_should_chart(query: str, route: dict[str, Any] | None = None, month_limit: int | None = None) -> bool:
    effective = _openai_intel_effective_query(query, route).lower()
    current = str(query or "").lower()

    if _final_is_chart_query(query, route) or _final_is_chart_query(effective, route):
        return True

    if month_limit and month_limit >= 2:
        return True

    if re.search(r"last\s+\d+\s+months?", current) or re.search(r"last\s+\d+\s+months?", effective):
        return True

    if any(term in effective for term in [
        "monthly", "month wise", "month-wise", "trend", "over time",
        "last few months", "past few months", "last several months",
    ]):
        return True

    return False


def _openai_gpt54mini_normalized_intent(query: str, route: dict[str, Any] | None, current_intent: str) -> str | None:
    route = route or {}
    effective = _openai_intel_effective_query(query, route)
    q = effective.lower().strip()

    if _final_is_chart_query(effective, route) and any(term in q for term in [
        "all chart", "all charts", "available chart", "available charts", "widgets", "dashboard"
    ]):
        return "dashboard_charts"

    resource = _openai_gpt54mini_resource_from_query(query, route)
    companies = _openai_gpt54mini_route_companies(query, route)

    if resource == "sales":
        if len(companies) > 1 or _final_is_comparison_query(effective, route):
            return "tenant_comparison"

        if _openai_gpt54mini_detail_or_date_query(query):
            return "record_lookup"

        return "sales_analysis"

    if resource:
        return "record_lookup"

    # Recover short follow-ups instead of out_of_scope.
    if _openai_intel_is_short_followup(query):
        if any(term in q for term in ["sale", "sales", "sold", "vehicle", "vehicles", "car", "cars"]):
            return "sales_analysis"

    if current_intent in VALID_INTENTS:
        return current_intent

    return None


def _openai_gpt54mini_apply_period(filters: dict[str, Any], query: str, route: dict[str, Any] | None = None) -> tuple[dict[str, Any], str, int | None]:
    time_filter, time_text, month_limit = _openai_gpt54mini_time_filter(query, route)
    final_filters = dict(filters)
    final_filters.update(time_filter)
    return final_filters, time_text, month_limit


def _openai_intel_scope(query: str, route: dict[str, Any] | None = None) -> tuple[str | None, str | None, str]:
    route = route or {}
    effective = _openai_intel_effective_query(query, route)

    company_id, company_name = _resolve_company_scope(effective, route)

    if company_name:
        return company_id, company_name, company_name

    return company_id, company_name, "all allowed companies"


def _build_sales_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}
    effective = _openai_intel_effective_query(query, route)
    company_id, company_name, display_name = _openai_intel_scope(query, route)

    base_filters: dict[str, Any] = {"status": ["!=", "Cancelled"]}
    if company_id:
        base_filters["company_id"] = company_id

    filters, time_text, month_limit = _openai_gpt54mini_apply_period(base_filters, query, route)

    rows = frappe.get_all(
        "DMS Vehicle Sale",
        filters=filters,
        fields=_existing_fields(
            "DMS Vehicle Sale",
            ["name", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "status", "creation"],
        ),
        order_by="creation asc",
    )

    is_count = _openai_gpt54mini_sales_count_query(effective, route)
    chart_needed = _openai_gpt54mini_should_chart(query, route, month_limit)

    if not rows:
        return _no_data_response(
            "sales_analysis",
            "sales_count" if is_count else "sales",
            time_text,
            company_id,
            company_name,
            f"No vehicle sales data was found in the DMS database for {display_name} over {time_text}.",
        )

    if is_count:
        summary = _openai_gpt54mini_monthly_summary(rows, "name", count_mode=True, month_limit=month_limit)
        total_count = int(summary["total"])

        text_response = f"{display_name} sold {total_count:,} vehicle(s) over {time_text}."

        widgets_to_show: list[str] = []
        widget_payloads: dict[str, Any] = {}

        if chart_needed:
            widgets_to_show = ["generic_charts"]
            widget_payloads["generic_charts"] = {
                "title": "Vehicle Sales Count",
                "scope": display_name,
                "month_limit": month_limit or len(summary["labels"]),
                "charts": [{
                    "id": "vehicle_sales_count",
                    "title": "Vehicle sales count",
                    "description": f"Vehicle sales count for {display_name}",
                    "type": "bar",
                    "labels": summary["labels"],
                    "series": summary["series"],
                    "total": summary["total"],
                    "prefix": "",
                }],
                "data_source": "database",
            }

        return _base_response(
            intent="sales_analysis",
            metric="sales_count",
            time_range=time_text,
            company_id=company_id,
            company_name=company_name,
            widgets_to_show=widgets_to_show,
            text_response=text_response,
            widget_payloads=widget_payloads,
            other={"data_source": "database", "answer_type": "vehicle_sales_count"},
        )

    summary = _openai_gpt54mini_monthly_summary(rows, "final_price", count_mode=False, month_limit=month_limit)
    highest = summary.get("highest_month")
    highest_month = {"month": highest["month"], "sales": highest["final_price"]} if highest else None

    text_response = f"Total sales revenue for {display_name} over {time_text} was ₹{summary['total']:,.0f}."
    if highest_month:
        text_response += f" The highest month was {highest_month['month']} with ₹{highest_month['sales']:,.0f}."

    widgets_to_show: list[str] = []
    widget_payloads: dict[str, Any] = {}

    if chart_needed:
        widgets_to_show = ["sales_chart"]
        widget_payloads["sales_chart"] = {
            "labels": summary["labels"],
            "series": summary["series"],
            "total": summary["total"],
            "highest_month": highest_month,
        }

    return _base_response(
        intent="sales_analysis",
        metric="sales",
        time_range=time_text,
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=widgets_to_show,
        text_response=text_response,
        widget_payloads=widget_payloads,
        other={"data_source": "database", "answer_type": "sales_revenue"},
    )


def _openai_gpt54mini_company_values(query: str, route: dict[str, Any] | None, metric: str) -> tuple[list[str], list[float], str]:
    route = route or {}
    effective = _openai_intel_effective_query(query, route)
    time_filter, time_text, _month_limit = _openai_gpt54mini_time_filter(query, route)

    companies = _openai_gpt54mini_route_companies(effective, route)
    if not companies:
        companies = [row["company_name"] for row in frappe.get_all("DMS Company", fields=["company_name"], order_by="company_name asc")]

    labels: list[str] = []
    series: list[float] = []

    for company in companies:
        company_id = _company_id_from_name(company)
        if not company_id:
            continue

        filters: dict[str, Any] = {"company_id": company_id, "status": ["!=", "Cancelled"]}
        filters.update(time_filter)

        if metric == "sales_count":
            value = frappe.db.count("DMS Vehicle Sale", filters) or 0
        else:
            value = frappe.db.get_value("DMS Vehicle Sale", filters, "sum(final_price)") or 0

        labels.append(company)
        series.append(float(value))

    return labels, series, time_text


def _build_tenant_comparison_response(query: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    route = route or {}
    effective = _openai_intel_effective_query(query, route)

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

    is_count = _openai_gpt54mini_sales_count_query(effective, route)
    metric = "sales_count" if is_count else "sales_revenue"

    labels, series, time_text = _openai_gpt54mini_company_values(query, route, metric)

    if is_count:
        parts = [f"{label}: {int(value):,} vehicle(s)" for label, value in zip(labels, series)]
        text_response = f"Vehicle sales count over {time_text}: " + "; ".join(parts) + "."
        response_metric = "sales_count"

        widgets_to_show = ["generic_charts"] if labels else []
        widget_payloads = {
            "generic_charts": {
                "title": "Vehicle Sales Count Comparison",
                "scope": "selected tenants",
                "month_limit": _openai_intel_month_limit(query, route),
                "charts": [{
                    "id": "tenant_vehicle_sales_count",
                    "title": "Vehicle sales count by tenant",
                    "description": f"Vehicle sales count over {time_text}",
                    "type": "bar",
                    "labels": labels,
                    "series": series,
                    "total": sum(series),
                    "prefix": "",
                }],
                "data_source": "database",
            }
        } if labels else {}

    else:
        parts = [f"{label}: ₹{value:,.0f}" for label, value in zip(labels, series)]
        text_response = f"Sales revenue comparison over {time_text}: " + "; ".join(parts) + "."
        response_metric = "sales"

        widgets_to_show = ["tenant_comparison_chart"] if labels else []
        widget_payloads = {
            "tenant_comparison_chart": {
                "labels": labels,
                "series": series,
            }
        } if labels else {}

    return _base_response(
        intent="tenant_comparison",
        metric=response_metric,
        time_range=time_text,
        company_id=None,
        company_name=None,
        widgets_to_show=widgets_to_show,
        text_response=text_response,
        widget_payloads=widget_payloads,
        other={"data_source": "database", "answer_type": response_metric},
    )

# OPENAI_INTELLIGENCE_V2_PATCH_END

# OPENAI_DATA_AGENT_PATCH_START

OPENAI_DATA_AGENT_MAX_ROWS_PER_RESOURCE = int(os.getenv("OPENAI_DATA_AGENT_MAX_ROWS_PER_RESOURCE", "1000"))


def _data_agent_provider_config() -> tuple[str, str | None, str]:
    if "_openai_gpt54mini_provider_config" in globals():
        return _openai_gpt54mini_provider_config()

    provider = (
        os.getenv("LLM_PROVIDER")
        or frappe.conf.get("llm_provider")
        or frappe.conf.get("LLM_PROVIDER")
        or "gemini"
    )
    provider = str(provider).strip().lower()

    api_key = (
        os.getenv("OPENAI_API_KEY")
        or frappe.conf.get("openai_api_key")
        or frappe.conf.get("OPENAI_API_KEY")
    )

    model = (
        os.getenv("OPENAI_MODEL")
        or frappe.conf.get("openai_model")
        or frappe.conf.get("OPENAI_MODEL")
        or "gpt-5.4-mini"
    )

    return provider, api_key, str(model).strip() or "gpt-5.4-mini"


def _data_agent_catalog() -> dict[str, dict[str, str]]:
    return {
        "leads": {"doctype": "DMS Lead", "title": "Leads"},
        "customers": {"doctype": "DMS Customer", "title": "Customers"},
        "sales": {"doctype": "DMS Vehicle Sale", "title": "Vehicle Sales"},
        "bookings": {"doctype": "DMS Booking", "title": "Bookings"},
        "test_drives": {"doctype": "DMS Test Drive", "title": "Test Drives"},
        "service_jobs": {"doctype": "DMS Service Job", "title": "Service Jobs"},
        "invoices": {"doctype": "DMS Invoice", "title": "Invoices"},
        "vehicles": {"doctype": "DMS Vehicle", "title": "Vehicles / Inventory"},
    }


def _data_agent_clean_value(value: Any) -> Any:
    if value is None:
        return None

    try:
        from decimal import Decimal
        if isinstance(value, Decimal):
            return float(value)
    except Exception:
        pass

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def _data_agent_has_field(doctype: str, fieldname: str) -> bool:
    try:
        if fieldname in {"name", "creation", "modified", "owner"}:
            return True
        return bool(frappe.get_meta(doctype).has_field(fieldname))
    except Exception:
        return False


def _data_agent_allowed_fields(doctype: str) -> list[str]:
    allowed = ["name", "creation", "modified", "owner"]

    fieldtypes = {
        "Data", "Link", "Dynamic Link", "Select", "Date", "Datetime",
        "Currency", "Int", "Float", "Percent", "Check", "Text",
        "Small Text", "Long Text", "Phone", "Email", "Read Only",
    }

    try:
        meta = frappe.get_meta(doctype)
        for df in meta.fields:
            if not df.fieldname:
                continue
            if df.fieldtype not in fieldtypes:
                continue
            if df.fieldname not in allowed:
                allowed.append(df.fieldname)
    except Exception:
        pass

    # Ensure common fields are included if present.
    common = [
        "company_id", "company_name",
        "customer_name", "lead_name", "contact_name",
        "mobile_no", "phone", "email",
        "vehicle_name", "model", "variant", "color", "stock_status",
        "status", "payment_status",
        "final_price", "total_amount", "booking_amount",
        "invoice_no", "invoice_type", "due_date",
        "booking_date", "expected_delivery",
        "scheduled_date", "scheduled_time",
        "service_type", "vehicle_reg_no",
        "source", "vehicle_interest",
    ]

    for field in common:
        if field not in allowed and _data_agent_has_field(doctype, field):
            allowed.append(field)

    return allowed


def _data_agent_company_name(company_id: str | None) -> str | None:
    if not company_id:
        return None

    try:
        return _company_name_from_id(company_id)
    except Exception:
        try:
            return frappe.db.get_value("DMS Company", company_id, "company_name")
        except Exception:
            return None


def _data_agent_current_scope() -> tuple[bool, str | None, str | None]:
    try:
        if _is_admin():
            return True, None, None
    except Exception:
        pass

    try:
        company_id, company_name = _user_company_scope()
        return False, company_id, company_name
    except Exception:
        return False, None, None


def _data_agent_company_mentions(query_text: str) -> list[str]:
    try:
        mentions = _final_company_mentions(query_text)
        return [m for m in mentions if m]
    except Exception:
        q = str(query_text or "").lower()
        found = []
        if "honda" in q:
            found.append("Honda")
        if "nexa" in q:
            found.append("NEXA")
        if "jaguar" in q:
            found.append("Jaguar")
        return found


def _data_agent_cross_tenant_denial(query_text: str) -> dict[str, Any] | None:
    is_admin, company_id, company_name = _data_agent_current_scope()

    if is_admin:
        return None

    company_name = company_name or "your tenant"
    q = str(query_text or "").lower()

    if any(term in q for term in ["all companies", "all tenants", "other companies", "other tenants", "cross tenant", "cross-company"]):
        return _base_response(
            intent="unauthorized",
            metric=None,
            time_range=None,
            company_id=company_id,
            company_name=company_name,
            widgets_to_show=[],
            text_response=f"You only have access to {company_name} information.",
            widget_payloads={},
            other={"access_decision": "denied", "reason": "cross_tenant_request"},
        )

    mentions = _data_agent_company_mentions(query_text)
    for mentioned in mentions:
        if company_name and mentioned.lower() != company_name.lower():
            return _base_response(
                intent="unauthorized",
                metric=None,
                time_range=None,
                company_id=company_id,
                company_name=company_name,
                widgets_to_show=[],
                text_response=f"You only have access to {company_name} information.",
                widget_payloads={},
                other={"access_decision": "denied", "reason": "cross_tenant_request"},
            )

    return None


def _data_agent_filters_for_doctype(doctype: str) -> dict[str, Any] | None:
    is_admin, company_id, _company_name = _data_agent_current_scope()

    if is_admin:
        return {}

    # Tenant users must never receive cross-tenant rows.
    if company_id and _data_agent_has_field(doctype, "company_id"):
        return {"company_id": company_id}

    # If a tenant-scoped doctype cannot be filtered by company_id, skip it.
    return None


def _data_agent_fetch_rows(resource: str, doctype: str) -> list[dict[str, Any]]:
    fields = _data_agent_allowed_fields(doctype)
    filters = _data_agent_filters_for_doctype(doctype)

    if filters is None:
        return []

    try:
        rows = frappe.get_all(
            doctype,
            filters=filters,
            fields=fields,
            order_by="creation desc",
            limit_page_length=OPENAI_DATA_AGENT_MAX_ROWS_PER_RESOURCE,
        )
    except Exception:
        rows = []

    cleaned: list[dict[str, Any]] = []

    for row in rows:
        item = {}
        for key, value in dict(row).items():
            item[key] = _data_agent_clean_value(value)

        if item.get("company_id") and not item.get("company_name"):
            item["company_name"] = _data_agent_company_name(item.get("company_id"))

        item["_resource"] = resource
        item["_doctype"] = doctype
        cleaned.append(item)

    return cleaned


def _data_agent_build_pack() -> dict[str, Any]:
    is_admin, company_id, company_name = _data_agent_current_scope()
    catalog = _data_agent_catalog()

    resources: dict[str, Any] = {}

    for resource, meta in catalog.items():
        doctype = meta["doctype"]
        fields = _data_agent_allowed_fields(doctype)
        rows = _data_agent_fetch_rows(resource, doctype)

        resources[resource] = {
            "doctype": doctype,
            "title": meta["title"],
            "fields": fields,
            "row_count": len(rows),
            "rows": rows,
        }

    return {
        "scope": {
            "is_admin": is_admin,
            "company_id": company_id,
            "company_name": company_name,
            "access_note": "Admin can see all companies." if is_admin else f"Tenant user can see only {company_name}.",
        },
        "resources": resources,
        "widget_policy": {
            "record_table": "Use for lists, records, search results, detail rows, contact lookup, invoices, vehicles, customers, leads, bookings, test drives, service jobs.",
            "generic_charts": "Use for count trends, revenue trends, comparisons, month-wise summaries, status breakdowns, and all chart requests.",
            "no_widget": "Use for simple direct answers like a single phone number, email, date, or one KPI where a chart/table adds no value.",
        },
    }


def _data_agent_output_schema() -> dict[str, Any]:
    resource_enum = list(_data_agent_catalog().keys())

    widget_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "widget_type": {
                "type": "string",
                "enum": ["none", "record_table", "generic_charts"],
            },
            "title": {"type": "string"},
            "resource": {
                "anyOf": [
                    {"type": "string", "enum": resource_enum},
                    {"type": "null"},
                ]
            },
            "record_names": {
                "type": "array",
                "items": {"type": "string"},
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
            },
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "pie", "none"],
            },
            "group_by": {
                "type": "string",
                "enum": ["month", "company", "field", "status", "none"],
            },
            "group_field": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "aggregation": {
                "type": "string",
                "enum": ["count", "sum", "none"],
            },
            "value_field": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "prefix": {"type": "string"},
            "suffix": {"type": "string"},
        },
        "required": [
            "widget_type",
            "title",
            "resource",
            "record_names",
            "fields",
            "chart_type",
            "group_by",
            "group_field",
            "aggregation",
            "value_field",
            "prefix",
            "suffix",
        ],
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "record_lookup",
                    "dashboard_charts",
                    "tenant_comparison",
                    "sales_analysis",
                    "service_analysis",
                    "inventory_analysis",
                    "knowledge_lookup",
                    "out_of_scope",
                ],
            },
            "answer": {"type": "string"},
            "metric": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "time_range": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "company_name": {
                "anyOf": [{"type": "string"}, {"type": "null"}]
            },
            "widgets": {
                "type": "array",
                "items": widget_schema,
            },
            "confidence": {"type": "number"},
        },
        "required": [
            "intent",
            "answer",
            "metric",
            "time_range",
            "company_name",
            "widgets",
            "confidence",
        ],
    }


def _data_agent_prompt(user_query: str, conversation_context: str | None, data_pack: dict[str, Any]) -> str:
    compact_pack = json.dumps(data_pack, ensure_ascii=False, default=str)

    return f"""
You are Vividity, a GPT data agent for a Dealer Management System.

You are given:
1. The user's question.
2. Conversation context.
3. A JSON data pack containing only database rows the current user is authorised to see.

Answer strictly from the data pack. Do not invent values.
If the exact answer is not present in the data pack, say that the matching data was not found.

Security rules:
- The data pack is already tenant-scoped by the backend.
- Never claim access to data not present in the data pack.
- If a tenant-scoped data pack contains only one company, answer only from that company.

Data reasoning rules:
- You may inspect all resources and all fields in the data pack.
- For customer join date, created date, or onboarding date, use a dedicated field if present; otherwise use "creation".
- For phone/contact/email questions, search customers first, then leads.
- For inventory stock questions, inspect vehicles and stock_status/status fields.
- For sales/sold vehicle questions, inspect vehicle sales.
- "sales", "number of sales", "cars sold", and "vehicles sold" normally mean vehicle sale count unless the user explicitly asks revenue/amount/income.
- Revenue/amount questions should use fields like final_price, total_amount, booking_amount when relevant.
- Time filtering must use date/datetime fields such as creation, booking_date, scheduled_date, due_date, expected_delivery where relevant.
- For vague follow-ups, use the conversation context.

Widget rules:
- Do not show a widget for a single direct answer such as one phone number, one email, one date, or one simple sentence.
- Use record_table for lists, details, search results, inventory rows, invoice rows, customer rows, lead rows, booking rows, service rows, or sales records.
- Use generic_charts for trends, comparisons, month-wise summaries, status breakdowns, sales over time, revenue over time, or "show chart/all charts" questions.
- Multiple charts are allowed by returning multiple generic_charts widget specs.
- Only return widgets that are useful for the answer.
- For each widget, include record_names from the rows used when possible.
- For record_table widgets, include the fields that should be displayed.
- For chart widgets:
  - aggregation=count for counts.
  - aggregation=sum for revenue/amount totals.
  - group_by=month for month-wise/time trend.
  - group_by=company for tenant/company comparisons.
  - group_by=status or field for breakdowns.
  - prefix="₹" for money charts, otherwise prefix="".

User question:
{user_query}

Conversation context:
{conversation_context or ""}

Authorised DMS data pack:
{compact_pack}
""".strip()


def _data_agent_extract_openai_text(response_json: dict[str, Any]) -> str | None:
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]

    pieces: list[str] = []
    for item in response_json.get("output") or []:
        for content in item.get("content") or []:
            if isinstance(content.get("text"), str):
                pieces.append(content["text"])

    if pieces:
        return "\n".join(pieces)

    return None


def _data_agent_call_openai(user_query: str, conversation_context: str | None, data_pack: dict[str, Any]) -> dict[str, Any]:
    _provider, api_key, model = _data_agent_provider_config()

    if not api_key:
        return {
            "_llm_status": "missing_api_key",
            "_llm_error": "openai_api_key/OPENAI_API_KEY not found in environment or site config",
            "_llm_provider": "openai",
            "_llm_model": model,
        }

    payload = {
        "model": model,
        "input": _data_agent_prompt(user_query, conversation_context, data_pack),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "dms_data_agent_answer",
                "strict": True,
                "schema": _data_agent_output_schema(),
            }
        },
        "store": False,
    }

    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read().decode("utf-8")
            response_json = json.loads(raw)

        output_text = _data_agent_extract_openai_text(response_json)
        parsed = _safe_json_loads(output_text)

        if not isinstance(parsed, dict):
            return {
                "_llm_status": "invalid_response",
                "_llm_error": "OpenAI returned empty or non-dict JSON",
                "_llm_provider": "openai",
                "_llm_model": model,
            }

        parsed["_llm_status"] = "ok"
        parsed["_llm_error"] = None
        parsed["_llm_provider"] = "openai"
        parsed["_llm_model"] = model
        return parsed

    except Exception as exc:
        return {
            "_llm_status": "call_failed",
            "_llm_error": str(exc)[:1000],
            "_llm_provider": "openai",
            "_llm_model": model,
        }


def _data_agent_rows_for_resource(data_pack: dict[str, Any], resource: str | None) -> list[dict[str, Any]]:
    if not resource:
        return []

    try:
        return list(data_pack["resources"][resource]["rows"])
    except Exception:
        return []


def _data_agent_filter_by_names(rows: list[dict[str, Any]], names: list[str] | None) -> list[dict[str, Any]]:
    if not names:
        return rows

    wanted = {str(name) for name in names if name}
    if not wanted:
        return rows

    filtered = [row for row in rows if str(row.get("name")) in wanted]

    return filtered if filtered else rows


def _data_agent_field_label(fieldname: str) -> str:
    if not fieldname:
        return ""
    return fieldname.replace("_", " ").strip().title()


def _data_agent_table_payload(widget: dict[str, Any], data_pack: dict[str, Any]) -> dict[str, Any] | None:
    resource = widget.get("resource")
    if not resource:
        return None

    resources = data_pack.get("resources") or {}
    resource_info = resources.get(resource) or {}
    rows = _data_agent_rows_for_resource(data_pack, resource)
    rows = _data_agent_filter_by_names(rows, widget.get("record_names") or [])

    fields = [field for field in (widget.get("fields") or []) if isinstance(field, str) and field]

    if not fields:
        fields = list((resource_info.get("fields") or [])[:8])

    # Keep tenant visible for admin if available.
    is_admin = (data_pack.get("scope") or {}).get("is_admin")
    if is_admin and "company_name" not in fields:
        fields = ["company_name"] + fields

    fields = [field for field in fields if field in (resource_info.get("fields") or []) or field in {"company_name", "_resource", "_doctype"}]
    fields = fields[:10]

    table_rows: list[dict[str, Any]] = []
    for row in rows[:10]:
        item = {"id": row.get("name")}
        for field in fields:
            item[field] = row.get(field)
        table_rows.append(item)

    columns = [{"key": field, "label": _data_agent_field_label(field)} for field in fields]

    return {
        "title": widget.get("title") or resource_info.get("title") or "Records",
        "resource": resource,
        "doctype": resource_info.get("doctype"),
        "columns": columns,
        "rows": table_rows,
        "total": len(rows),
        "shown": len(table_rows),
        "offset": 0,
        "search_text": None,
        "requested_fields": fields,
        "data_source": "database",
    }


def _data_agent_group_label(row: dict[str, Any], widget: dict[str, Any]) -> str:
    group_by = widget.get("group_by")
    group_field = widget.get("group_field")

    if group_by == "month":
        for field in [group_field, "creation", "booking_date", "scheduled_date", "due_date", "expected_delivery"]:
            if field and row.get(field):
                return str(row.get(field))[:7]
        return "Unknown"

    if group_by == "company":
        return str(row.get("company_name") or _data_agent_company_name(row.get("company_id")) or "Unknown")

    if group_by == "status":
        return str(row.get("status") or row.get("payment_status") or row.get("stock_status") or "Unknown")

    if group_by == "field" and group_field:
        return str(row.get(group_field) or "Unknown")

    return "Total"


def _data_agent_numeric_value(row: dict[str, Any], fieldname: str | None) -> float:
    if not fieldname:
        return 0.0

    value = row.get(fieldname)

    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _data_agent_chart_from_widget(widget: dict[str, Any], data_pack: dict[str, Any]) -> dict[str, Any] | None:
    resource = widget.get("resource")
    if not resource:
        return None

    rows = _data_agent_rows_for_resource(data_pack, resource)
    rows = _data_agent_filter_by_names(rows, widget.get("record_names") or [])

    aggregation = widget.get("aggregation") or "count"
    value_field = widget.get("value_field")

    totals: dict[str, float] = {}

    for row in rows:
        label = _data_agent_group_label(row, widget)
        if label not in totals:
            totals[label] = 0.0

        if aggregation == "sum":
            totals[label] += _data_agent_numeric_value(row, value_field)
        else:
            totals[label] += 1.0

    labels = sorted(totals.keys())
    series = [totals[label] for label in labels]

    if not labels:
        return None

    chart_type = widget.get("chart_type") or "bar"
    if chart_type == "none":
        chart_type = "bar"

    return {
        "id": re.sub(r"[^a-z0-9_]+", "_", str(widget.get("title") or resource).lower()).strip("_") or "chart",
        "title": widget.get("title") or "Chart",
        "description": widget.get("title") or "DMS chart",
        "type": chart_type,
        "labels": labels,
        "series": series,
        "total": sum(series),
        "prefix": widget.get("prefix") or "",
        "suffix": widget.get("suffix") or "",
    }


def _data_agent_build_widgets(plan: dict[str, Any], data_pack: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    widgets = plan.get("widgets") or []

    widgets_to_show: list[str] = []
    widget_payloads: dict[str, Any] = {}

    record_table_payload: dict[str, Any] | None = None
    charts: list[dict[str, Any]] = []

    for widget in widgets:
        if not isinstance(widget, dict):
            continue

        widget_type = widget.get("widget_type")

        if widget_type == "record_table" and record_table_payload is None:
            record_table_payload = _data_agent_table_payload(widget, data_pack)

        if widget_type == "generic_charts":
            chart = _data_agent_chart_from_widget(widget, data_pack)
            if chart:
                charts.append(chart)

    if record_table_payload:
        widgets_to_show.append("record_table")
        widget_payloads["record_table"] = record_table_payload

    if charts:
        widgets_to_show.append("generic_charts")
        widget_payloads["generic_charts"] = {
            "title": "DMS Data Charts",
            "scope": (data_pack.get("scope") or {}).get("company_name") or "all allowed companies",
            "month_limit": None,
            "charts": charts,
            "data_source": "database",
        }

    return widgets_to_show, widget_payloads


def _data_agent_llm_error(route: dict[str, Any], user_query: str) -> dict[str, Any]:
    return _base_response(
        intent="backend_llm_error",
        metric=None,
        time_range=None,
        company_id=None,
        company_name=None,
        widgets_to_show=[],
        text_response="Sorry, the backend LLM is not working right now. Please try again shortly.",
        widget_payloads={},
        other={
            "llm_required": True,
            "llm_provider": route.get("_llm_provider"),
            "llm_model": route.get("_llm_model"),
            "llm_status": route.get("_llm_status"),
            "llm_error": route.get("_llm_error"),
            "routing_query": user_query,
        },
    )


def _data_agent_response(plan: dict[str, Any], data_pack: dict[str, Any], user_query: str) -> dict[str, Any]:
    widgets_to_show, widget_payloads = _data_agent_build_widgets(plan, data_pack)

    scope = data_pack.get("scope") or {}
    company_id = scope.get("company_id")
    company_name = plan.get("company_name") or scope.get("company_name")

    intent = plan.get("intent") if plan.get("intent") in VALID_INTENTS else "record_lookup"

    answer = str(plan.get("answer") or "").strip()
    if not answer:
        answer = "I could not find a matching answer in the authorised DMS data."

    return _base_response(
        intent=intent,
        metric=plan.get("metric"),
        time_range=plan.get("time_range"),
        company_id=company_id,
        company_name=company_name,
        widgets_to_show=widgets_to_show,
        text_response=answer,
        widget_payloads=widget_payloads,
        other={
            "data_source": "authorised_dms_data_pack",
            "answer_type": "openai_data_agent",
            "llm_required": True,
            "llm_provider": plan.get("_llm_provider"),
            "llm_model": plan.get("_llm_model"),
            "llm_status": plan.get("_llm_status"),
            "llm_error": plan.get("_llm_error"),
            "llm_confidence": plan.get("confidence"),
            "routing_query": user_query,
            "resources_visible": {
                key: value.get("row_count")
                for key, value in (data_pack.get("resources") or {}).items()
            },
        },
    )


def _data_agent_request_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {}

    try:
        if getattr(frappe, "request", None):
            incoming = frappe.request.get_json(silent=True) or {}
            if isinstance(incoming, dict):
                payload.update(incoming)
    except Exception:
        pass

    try:
        payload.update(dict(frappe.form_dict or {}))
    except Exception:
        pass

    return payload


_OPENAI_DATA_AGENT_PREVIOUS_QUERY = globals().get("query")


@frappe.whitelist(allow_guest=True)
def query(query: str | None = None, conversation_context: str | None = None, **kwargs):
    provider, _api_key, _model = _data_agent_provider_config()

    # Keep old behavior if provider is not OpenAI.
    if provider != "openai":
        previous = globals().get("_OPENAI_DATA_AGENT_PREVIOUS_QUERY")
        if callable(previous):
            try:
                return previous(query=query, conversation_context=conversation_context, **kwargs)
            except TypeError:
                return previous()
        return success(data=_final_out_of_scope_response())

    payload = _data_agent_request_payload()
    payload.update(kwargs or {})

    user_query = (
        query
        or payload.get("query")
        or payload.get("message")
        or payload.get("text")
        or ""
    )
    user_query = str(user_query or "").strip()

    conversation_context = (
        conversation_context
        or payload.get("conversation_context")
        or payload.get("context")
        or ""
    )

    if not user_query:
        data = _base_response(
            intent="out_of_scope",
            metric=None,
            time_range=None,
            company_id=None,
            company_name=None,
            widgets_to_show=[],
            text_response="Please ask a DMS data question.",
            widget_payloads={},
            other={"answer_type": "empty_query"},
        )
        return success(data=data)

    denial = _data_agent_cross_tenant_denial(user_query)
    if denial:
        return success(data=denial)

    data_pack = _data_agent_build_pack()
    plan = _data_agent_call_openai(user_query, conversation_context, data_pack)

    if plan.get("_llm_status") != "ok":
        return success(data=_data_agent_llm_error(plan, user_query))

    data = _data_agent_response(plan, data_pack, user_query)
    return success(data=data)

# OPENAI_DATA_AGENT_PATCH_END

# FOCUSED_OPENAI_DATA_AGENT_PATCH_START

FOCUSED_DATA_AGENT_ROW_LIMITS = {
    "customers": 300,
    "leads": 300,
    "sales": 450,
    "invoices": 450,
    "bookings": 300,
    "test_drives": 300,
    "service_jobs": 220,
    "vehicles": 220,
}


def _focused_da_lower(value: str | None) -> str:
    return str(value or "").lower().strip()


def _focused_da_has_any(text: str | None, terms: list[str]) -> bool:
    q = _focused_da_lower(text)
    return any(term in q for term in terms)


def _focused_da_resources_for_query(user_query: str, conversation_context: str | None = None) -> list[str]:
    q = _focused_da_lower((conversation_context or "") + "\n" + (user_query or ""))

    if _focused_da_has_any(q, ["phone", "mobile", "contact number", "email", "mail", "join", "joined", "customer"]):
        return ["customers", "leads", "sales", "bookings", "test_drives", "service_jobs", "invoices"]

    if _focused_da_has_any(q, ["inventory", "stock", "vehicle stock", "available vehicle", "available car"]):
        return ["vehicles", "sales", "bookings"]

    if _focused_da_has_any(q, ["sale", "sales", "sold", "revenue", "income", "amount", "invoice"]):
        return ["sales", "invoices", "customers", "vehicles"]

    if _focused_da_has_any(q, ["booking", "booked", "delivery"]):
        return ["bookings", "customers", "vehicles", "sales"]

    if _focused_da_has_any(q, ["test drive", "testdrive", "scheduled"]):
        return ["test_drives", "customers", "leads", "vehicles"]

    if _focused_da_has_any(q, ["service", "job", "repair", "pending jobs", "completed jobs"]):
        return ["service_jobs", "customers", "vehicles"]

    if _focused_da_has_any(q, ["chart", "graph", "trend", "month", "months", "year", "years", "dashboard", "widget"]):
        return ["sales", "invoices", "leads", "bookings", "test_drives", "service_jobs", "vehicles", "customers"]

    return ["customers", "leads", "sales", "invoices", "bookings", "test_drives", "service_jobs", "vehicles"]


def _focused_da_minimal_fields(resource: str, doctype: str) -> list[str]:
    preferred = {
        "customers": ["name", "creation", "company_id", "company_name", "customer_name", "customer_type", "mobile_no", "email", "status"],
        "leads": ["name", "creation", "company_id", "company_name", "lead_name", "mobile_no", "email", "status", "source", "vehicle_interest"],
        "sales": ["name", "creation", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "status", "invoice_no"],
        "invoices": ["name", "creation", "company_id", "company_name", "customer_name", "invoice_no", "invoice_type", "total_amount", "payment_status", "status", "due_date"],
        "bookings": ["name", "creation", "company_id", "company_name", "customer_name", "model", "variant", "booking_amount", "booking_date", "expected_delivery", "status"],
        "test_drives": ["name", "creation", "company_id", "company_name", "contact_name", "customer_name", "mobile_no", "email", "model", "scheduled_date", "scheduled_time", "status"],
        "service_jobs": ["name", "creation", "company_id", "company_name", "customer_name", "vehicle_reg_no", "model", "service_type", "total_amount", "status"],
        "vehicles": ["name", "creation", "company_id", "company_name", "vehicle_name", "model", "variant", "color", "stock_status", "status"],
    }

    fields = []
    for field in preferred.get(resource, ["name", "creation", "company_id", "company_name", "status"]):
        try:
            if _data_agent_has_field(doctype, field):
                fields.append(field)
        except Exception:
            pass

    return fields or ["name", "creation"]


def _focused_da_fetch_rows(resource: str, doctype: str, limit: int) -> list[dict[str, Any]]:
    fields = _focused_da_minimal_fields(resource, doctype)

    filters = _data_agent_filters_for_doctype(doctype)
    if filters is None:
        return []

    try:
        rows = frappe.get_all(
            doctype,
            filters=filters,
            fields=fields,
            order_by="creation desc",
            limit_page_length=limit,
        )
    except Exception:
        return []

    cleaned = []
    for row in rows:
        item = {}
        for key, value in dict(row).items():
            item[key] = _data_agent_clean_value(value)

        if item.get("company_id") and not item.get("company_name"):
            item["company_name"] = _data_agent_company_name(item.get("company_id"))

        item["_resource"] = resource
        item["_doctype"] = doctype
        cleaned.append(item)

    return cleaned


def _focused_da_month_label(value: Any) -> str:
    if not value:
        return "Unknown"
    return str(value)[:7]


def _focused_da_amount(row: dict[str, Any]) -> float:
    for field in ["final_price", "total_amount", "booking_amount"]:
        try:
            if row.get(field) not in (None, ""):
                return float(row.get(field) or 0)
        except Exception:
            pass
    return 0.0


def _focused_da_resource_summary(resource: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_company: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_month_count: dict[str, int] = {}
    by_month_amount: dict[str, float] = {}

    for row in rows:
        company = str(row.get("company_name") or row.get("company_id") or "Unknown")
        status = str(row.get("status") or row.get("payment_status") or row.get("stock_status") or "Unknown")
        month = _focused_da_month_label(row.get("creation"))

        by_company[company] = by_company.get(company, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        by_month_count[month] = by_month_count.get(month, 0) + 1
        by_month_amount[month] = by_month_amount.get(month, 0.0) + _focused_da_amount(row)

    return {
        "row_count_in_pack": len(rows),
        "by_company": by_company,
        "by_status": by_status,
        "by_month_count": dict(sorted(by_month_count.items())),
        "by_month_amount": dict(sorted(by_month_amount.items())),
    }


def _focused_da_build_pack(user_query: str, conversation_context: str | None = None) -> dict[str, Any]:
    is_admin, company_id, company_name = _data_agent_current_scope()
    catalog = _data_agent_catalog()
    selected_resources = _focused_da_resources_for_query(user_query, conversation_context)

    resources: dict[str, Any] = {}

    for resource in selected_resources:
        meta = catalog.get(resource)
        if not meta:
            continue

        doctype = meta["doctype"]
        limit = FOCUSED_DATA_AGENT_ROW_LIMITS.get(resource, 150)
        rows = _focused_da_fetch_rows(resource, doctype, limit)

        resources[resource] = {
            "doctype": doctype,
            "title": meta["title"],
            "fields": _focused_da_minimal_fields(resource, doctype),
            "row_count": len(rows),
            "limit_applied": limit,
            "summary": _focused_da_resource_summary(resource, rows),
            "rows": rows,
        }

    return {
        "scope": {
            "is_admin": is_admin,
            "company_id": company_id,
            "company_name": company_name,
            "access_note": "Admin can see all companies." if is_admin else f"Tenant user can see only {company_name}.",
        },
        "resources": resources,
        "widget_policy": {
            "record_table": "Use for lists, records, search results, detail rows, contact lookup, invoices, vehicles, customers, leads, bookings, test drives, service jobs.",
            "generic_charts": "Use for count trends, revenue trends, comparisons, month-wise summaries, status breakdowns, and all chart requests.",
            "no_widget": "Use for simple direct answers like a single phone number, email, date, or one KPI where a chart/table adds no value.",
        },
    }


def _data_agent_call_openai(user_query: str, conversation_context: str | None, data_pack: dict[str, Any]) -> dict[str, Any]:
    _provider, api_key, model = _data_agent_provider_config()

    if not api_key:
        return {
            "_llm_status": "missing_api_key",
            "_llm_error": "openai_api_key/OPENAI_API_KEY not found in environment or site config",
            "_llm_provider": "openai",
            "_llm_model": model,
        }

    payload = {
        "model": model,
        "input": _data_agent_prompt(user_query, conversation_context, data_pack),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "dms_data_agent_answer",
                "strict": True,
                "schema": _data_agent_output_schema(),
            }
        },
        "store": False,
    }

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read().decode("utf-8")
            response_json = json.loads(raw)

        output_text = _data_agent_extract_openai_text(response_json)
        parsed = _safe_json_loads(output_text)

        if not isinstance(parsed, dict):
            return {
                "_llm_status": "invalid_response",
                "_llm_error": "OpenAI returned empty or non-dict JSON",
                "_llm_provider": "openai",
                "_llm_model": model,
            }

        parsed["_llm_status"] = "ok"
        parsed["_llm_error"] = None
        parsed["_llm_provider"] = "openai"
        parsed["_llm_model"] = model
        return parsed

    except Exception as exc:
        error_detail = str(exc)[:2000]

        try:
            import urllib.error
            if isinstance(exc, urllib.error.HTTPError):
                body = exc.read().decode("utf-8", errors="replace")
                error_detail = f"HTTP {exc.code}: {body[:2000]}"
        except Exception:
            pass

        return {
            "_llm_status": "call_failed",
            "_llm_error": error_detail,
            "_llm_provider": "openai",
            "_llm_model": model,
        }


@frappe.whitelist(allow_guest=True)
def query(query: str | None = None, conversation_context: str | None = None, **kwargs):
    provider, _api_key, _model = _data_agent_provider_config()

    if provider != "openai":
        previous = globals().get("_OPENAI_DATA_AGENT_PREVIOUS_QUERY")
        if callable(previous):
            try:
                return previous(query=query, conversation_context=conversation_context, **kwargs)
            except TypeError:
                return previous()
        return success(data=_final_out_of_scope_response())

    payload = _data_agent_request_payload()
    payload.update(kwargs or {})

    user_query = (
        query
        or payload.get("query")
        or payload.get("message")
        or payload.get("text")
        or ""
    )
    user_query = str(user_query or "").strip()

    conversation_context = (
        conversation_context
        or payload.get("conversation_context")
        or payload.get("context")
        or ""
    )

    if not user_query:
        data = _base_response(
            intent="out_of_scope",
            metric=None,
            time_range=None,
            company_id=None,
            company_name=None,
            widgets_to_show=[],
            text_response="Please ask a DMS data question.",
            widget_payloads={},
            other={"answer_type": "empty_query"},
        )
        return success(data=data)

    denial = _data_agent_cross_tenant_denial(user_query)
    if denial:
        return success(data=denial)

    data_pack = _focused_da_build_pack(user_query, conversation_context)
    plan = _data_agent_call_openai(user_query, conversation_context, data_pack)

    if plan.get("_llm_status") != "ok":
        return success(data=_data_agent_llm_error(plan, user_query))

    data = _data_agent_response(plan, data_pack, user_query)
    return success(data=data)

# FOCUSED_OPENAI_DATA_AGENT_PATCH_END

# OPTIMIZED_STRUCTURED_RAG_RANKING_PATCH_START

# Keep GPT context compact. Summaries still represent all fetched authorised rows.
RAG_ROW_LIMITS = {
    "customers": 25,
    "leads": 25,
    "sales": 80,
    "invoices": 60,
    "bookings": 50,
    "test_drives": 50,
    "service_jobs": 60,
    "vehicles": 60,
}

RAG_FETCH_LIMITS = {
    "customers": 1200,
    "leads": 1200,
    "sales": 1800,
    "invoices": 1400,
    "bookings": 1200,
    "test_drives": 1200,
    "service_jobs": 1600,
    "vehicles": 1200,
}


def _opt_rag_lower(value: str | None) -> str:
    return str(value or "").lower().strip()


def _opt_rag_has_any(text: str | None, terms: list[str]) -> bool:
    q = _opt_rag_lower(text)
    return any(term in q for term in terms)


def _opt_rag_tokens(text: str | None) -> list[str]:
    stop = {
        "what", "is", "the", "of", "for", "show", "tell", "me", "get", "give",
        "phone", "number", "mobile", "contact", "email", "mail", "when", "did",
        "join", "joined", "current", "chart", "graph", "sales", "sale", "last",
        "month", "months", "year", "years", "in", "and", "or", "all", "useful",
        "data", "details", "record", "records", "please", "customer", "lead",
        "vehicle", "vehicles", "car", "cars", "stock", "inventory", "status",
    }

    out = []
    for token in re.findall(r"[A-Za-z0-9]+", str(text or "").lower()):
        if len(token) < 2 or token in stop:
            continue
        out.append(token)

    return out[:12]


def _opt_rag_extract_name(query_text: str) -> str | None:
    if "_rag_extract_name" in globals():
        try:
            name = _rag_extract_name(query_text)
            if name:
                return name
        except Exception:
            pass

    q = str(query_text or "").strip()

    patterns = [
        r"(?:phone number|contact number|mobile number|mobile no|phone no|email|mail|join|joined|customer since|details)\s+(?:of|for)\s+(.+)$",
        r"(?:when did|when was)\s+(.+?)\s+(?:join|joined|created|added)",
        r"(?:what is|what's|show|tell me|get)\s+(?:the\s+)?(?:phone number|contact number|mobile number|email|mail|details)\s+(?:of|for)\s+(.+)$",
        r"(?:of|for)\s+([A-Za-z][A-Za-z .'-]{2,})\??$",
    ]

    for pattern in patterns:
        m = re.search(pattern, q, flags=re.I)
        if m:
            name = m.group(1).strip()
            name = re.sub(r"[?.,!]+$", "", name).strip()
            name = re.sub(r"\b(customer|lead|client)\b", "", name, flags=re.I).strip()
            return name or None

    return None


def _opt_rag_profile(user_query: str, conversation_context: str | None = None) -> dict[str, Any]:
    full = f"{conversation_context or ''}\n{user_query or ''}"
    q = _opt_rag_lower(full)
    current = _opt_rag_lower(user_query)

    name = _opt_rag_extract_name(user_query) or _opt_rag_extract_name(full)
    name_tokens = _opt_rag_tokens(name)
    query_tokens = _opt_rag_tokens(user_query)

    try:
        companies = _data_agent_company_mentions(full)
    except Exception:
        companies = []
        if "honda" in q:
            companies.append("Honda")
        if "nexa" in q:
            companies.append("NEXA")
        if "jaguar" in q:
            companies.append("Jaguar")

    is_contact = _opt_rag_has_any(q, ["phone", "mobile", "contact number", "email", "mail"])
    is_join = _opt_rag_has_any(q, ["join", "joined", "created", "added", "customer since"])
    is_inventory = _opt_rag_has_any(q, ["inventory", "stock", "available vehicle", "available car", "vehicle stock"])
    is_sales = _opt_rag_has_any(q, ["sale", "sales", "sold", "revenue", "income", "bought", "purchased"])
    is_invoice = _opt_rag_has_any(q, ["invoice", "payment", "paid", "unpaid", "due", "pending amount"])
    is_booking = _opt_rag_has_any(q, ["booking", "booked", "delivery"])
    is_test_drive = _opt_rag_has_any(q, ["test drive", "testdrive", "scheduled drive"])
    is_service = _opt_rag_has_any(q, ["service", "repair", "job", "jobs"])
    is_chart = _opt_rag_has_any(q, ["chart", "graph", "trend", "dashboard", "widget", "month wise", "month-wise", "over time"])

    wants_revenue = _opt_rag_has_any(q, ["revenue", "income", "amount", "total sales amount", "sales value"])
    wants_count = _opt_rag_has_any(q, ["how many", "number of", "count", "total number"]) or (is_sales and not wants_revenue)

    statuses = []
    for status in ["open", "pending", "active", "completed", "paid", "unpaid", "in stock", "sold"]:
        if status in q:
            statuses.append(status)

    return {
        "full_text": full,
        "current_text": current,
        "name": name,
        "name_tokens": name_tokens,
        "query_tokens": query_tokens,
        "companies": companies,
        "is_contact": is_contact,
        "is_join": is_join,
        "is_inventory": is_inventory,
        "is_sales": is_sales,
        "is_invoice": is_invoice,
        "is_booking": is_booking,
        "is_test_drive": is_test_drive,
        "is_service": is_service,
        "is_chart": is_chart,
        "wants_revenue": wants_revenue,
        "wants_count": wants_count,
        "statuses": statuses,
    }


def _rag_selected_resources(user_query: str, conversation_context: str | None = None) -> list[str]:
    p = _opt_rag_profile(user_query, conversation_context)

    # Exact contact/date lookup must not send sales/service/invoice noise.
    if p["is_contact"] or p["is_join"]:
        return ["customers", "leads"]

    if p["is_inventory"]:
        return ["vehicles", "bookings", "sales"]

    if p["is_invoice"]:
        return ["invoices", "customers", "sales"]

    if p["is_sales"]:
        return ["sales", "invoices", "customers", "vehicles"]

    if p["is_booking"]:
        return ["bookings", "customers", "vehicles", "sales"]

    if p["is_test_drive"]:
        return ["test_drives", "customers", "leads", "vehicles"]

    if p["is_service"]:
        return ["service_jobs", "customers", "vehicles"]

    if p["is_chart"]:
        return ["sales", "invoices", "leads", "bookings", "test_drives", "service_jobs", "vehicles"]

    return ["customers", "leads", "sales", "invoices", "vehicles"]


def _opt_rag_identity_fields(resource: str) -> list[str]:
    return {
        "customers": ["customer_name", "mobile_no", "email", "name"],
        "leads": ["lead_name", "mobile_no", "email", "name"],
        "sales": ["customer_name", "model", "variant", "invoice_no", "name"],
        "invoices": ["customer_name", "invoice_no", "invoice_type", "name"],
        "bookings": ["customer_name", "model", "variant", "name"],
        "test_drives": ["contact_name", "customer_name", "mobile_no", "email", "model", "name"],
        "service_jobs": ["customer_name", "vehicle_reg_no", "model", "service_type", "name"],
        "vehicles": ["vehicle_name", "model", "variant", "color", "stock_status", "name"],
    }.get(resource, ["name"])


def _opt_rag_row_field_text(row: dict[str, Any], fields: list[str]) -> str:
    return " ".join(str(row.get(field) or "") for field in fields).lower()


def _opt_rag_row_all_text(row: dict[str, Any]) -> str:
    return " ".join(str(v or "") for v in row.values()).lower()


def _opt_rag_company_score(row: dict[str, Any], companies: list[str]) -> int:
    if not companies:
        return 0

    row_company = str(row.get("company_name") or row.get("company_id") or "").lower()
    score = 0

    for company in companies:
        if company.lower() == row_company:
            score += 100
        elif company.lower() in row_company:
            score += 70

    return score


def _opt_rag_status_score(row: dict[str, Any], statuses: list[str]) -> int:
    if not statuses:
        return 0

    row_status = str(row.get("status") or row.get("payment_status") or row.get("stock_status") or "").lower()
    score = 0

    for status in statuses:
        if status == row_status:
            score += 80
        elif status in row_status:
            score += 50

    return score


def _rag_rank_rows(rows: list[dict[str, Any]], user_query: str) -> list[dict[str, Any]]:
    p = _opt_rag_profile(user_query)
    scored: list[tuple[int, int, dict[str, Any]]] = []

    for idx, row in enumerate(rows):
        resource = row.get("_resource") or ""
        identity_text = _opt_rag_row_field_text(row, _opt_rag_identity_fields(resource))
        all_text = _opt_rag_row_all_text(row)

        score = 0

        # Exact person/entity lookup: highest priority.
        if p["name_tokens"]:
            if all(token in identity_text for token in p["name_tokens"]):
                score += 500
            elif all(token in all_text for token in p["name_tokens"]):
                score += 350
            else:
                for token in p["name_tokens"]:
                    if token in identity_text:
                        score += 120
                    elif token in all_text:
                        score += 60

        # General query tokens.
        for token in p["query_tokens"]:
            if token in identity_text:
                score += 35
            elif token in all_text:
                score += 12

        score += _opt_rag_company_score(row, p["companies"])
        score += _opt_rag_status_score(row, p["statuses"])

        # Resource/intent weighting.
        if resource == "customers" and (p["is_contact"] or p["is_join"]):
            score += 200
        if resource == "leads" and p["is_contact"]:
            score += 120
        if resource == "sales" and p["is_sales"]:
            score += 160
        if resource == "invoices" and p["is_invoice"]:
            score += 160
        if resource == "vehicles" and p["is_inventory"]:
            score += 180
        if resource == "bookings" and p["is_booking"]:
            score += 160
        if resource == "test_drives" and p["is_test_drive"]:
            score += 160
        if resource == "service_jobs" and p["is_service"]:
            score += 160

        # For chart/trend questions, retain broader rows but still prioritize relevant resources.
        if p["is_chart"]:
            if resource in {"sales", "invoices", "leads", "bookings", "test_drives", "service_jobs", "vehicles"}:
                score += 40

        # Very small recency tie-breaker only; do not overpower exact entity match.
        creation = str(row.get("creation") or "")
        if creation:
            score += 1

        scored.append((score, -idx, row))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

    # If strong exact/entity matches exist, drop irrelevant zero-score rows.
    if any(score >= 250 for score, _idx, _row in scored):
        return [row for score, _idx, row in scored if score > 0]

    # For contact/join queries, do not send random unrelated rows if no match.
    if p["is_contact"] or p["is_join"]:
        return [row for score, _idx, row in scored if score > 0]

    return [row for _score, _idx, row in scored]


def _opt_rag_limit_for(resource: str, profile: dict[str, Any]) -> int:
    if profile["is_contact"] or profile["is_join"]:
        return 12 if resource in {"customers", "leads"} else 0

    if profile["is_chart"]:
        return {
            "sales": 40,
            "invoices": 30,
            "leads": 25,
            "bookings": 25,
            "test_drives": 25,
            "service_jobs": 30,
            "vehicles": 25,
        }.get(resource, 15)

    if profile["is_sales"]:
        return {"sales": 60, "invoices": 30, "customers": 25, "vehicles": 20}.get(resource, 20)

    if profile["is_inventory"]:
        return {"vehicles": 50, "bookings": 20, "sales": 20}.get(resource, 15)

    return RAG_ROW_LIMITS.get(resource, 30)


def _structured_rag_build_pack(user_query: str, conversation_context: str | None = None) -> dict[str, Any]:
    is_admin, company_id, company_name = _data_agent_current_scope()
    catalog = _data_agent_catalog()
    profile = _opt_rag_profile(user_query, conversation_context)
    selected = _rag_selected_resources(user_query, conversation_context)

    resources: dict[str, Any] = {}

    for resource in selected:
        meta = catalog.get(resource)
        if not meta:
            continue

        doctype = meta["doctype"]
        all_rows = _rag_fetch_resource_rows(resource, doctype)
        ranked_rows = _rag_rank_rows(all_rows, user_query)
        keep = _opt_rag_limit_for(resource, profile)
        rows_for_llm = ranked_rows[:keep] if keep > 0 else []

        resources[resource] = {
            "doctype": doctype,
            "title": meta["title"],
            "fields": _rag_fields(resource, doctype),
            "row_count": len(rows_for_llm),
            "total_rows_available": len(all_rows),
            "summary": _rag_summary(all_rows),
            "rows": rows_for_llm,
        }

    return {
        "scope": {
            "is_admin": is_admin,
            "company_id": company_id,
            "company_name": company_name,
            "access_note": "Admin can see all companies." if is_admin else f"Tenant user can see only {company_name}.",
        },
        "retrieval": {
            "mode": "optimized_structured_database_rag",
            "selected_resources": selected,
            "query_profile": {
                "name": profile.get("name"),
                "companies": profile.get("companies"),
                "is_contact": profile.get("is_contact"),
                "is_join": profile.get("is_join"),
                "is_inventory": profile.get("is_inventory"),
                "is_sales": profile.get("is_sales"),
                "is_invoice": profile.get("is_invoice"),
                "is_chart": profile.get("is_chart"),
            },
            "note": "Rows are authorised, resource-filtered, field-weighted, ranked, and compacted before sending to GPT. Summaries are calculated from all fetched authorised rows.",
        },
        "resources": resources,
        "widget_policy": {
            "record_table": "Use for lists, records, search results, detail rows, contact lookup, invoices, vehicles, customers, leads, bookings, test drives, service jobs.",
            "generic_charts": "Use for count trends, revenue trends, comparisons, month-wise summaries, status breakdowns, and all chart requests.",
            "no_widget": "Use for simple direct answers like a single phone number, email, date, or one KPI where a chart/table adds no value.",
        },
    }


def _data_agent_prompt(user_query: str, conversation_context: str | None, data_pack: dict[str, Any]) -> str:
    compact_pack = json.dumps(data_pack, ensure_ascii=False, default=str, separators=(",", ":"))

    return f"""
You are Vividity, a Dealer Management System data agent.

Answer only from the authorised DMS data pack. Do not invent values.
If the answer is not present, say the matching data was not found.

Security:
- The backend has already tenant-scoped the data pack.
- Never answer using data not present in the pack.

Reasoning:
- Customers/leads contain phone, email, join/created date, and contact details.
- For join/customer-since questions, use a dedicated join field if present; otherwise use creation.
- Sales/sold/cars sold usually means vehicle sale count unless revenue/amount/income is explicit.
- Revenue/amount uses final_price, total_amount, or booking_amount when relevant.
- For charts, use summaries and/or rows in the pack.
- For simple direct answers, do not request widgets.
- For lists/details, use record_table.
- For trends/comparisons/status breakdowns, use generic_charts.
- Multiple useful charts may be returned when the user asks for all useful charts/widgets.

User question:
{user_query}

Conversation context:
{conversation_context or ""}

Authorised DMS data pack:
{compact_pack}
""".strip()

# OPTIMIZED_STRUCTURED_RAG_RANKING_PATCH_END

# ULTRA_COMPACT_RAG_FINAL_PATCH_START

ULTRA_RAG_DETAIL_LIMIT = 12
ULTRA_RAG_CHART_ROW_LIMIT = 700
ULTRA_RAG_LIST_LIMIT = 80


def _ultra_lower(value: str | None) -> str:
    return str(value or "").lower().strip()


def _ultra_has_any(text: str | None, terms: list[str]) -> bool:
    q = _ultra_lower(text)
    return any(term in q for term in terms)


def _ultra_tokens(text: str | None) -> list[str]:
    stop = {
        "what", "is", "the", "of", "for", "show", "tell", "me", "get", "give",
        "phone", "number", "mobile", "contact", "email", "mail", "when", "did",
        "join", "joined", "created", "added", "current", "chart", "graph",
        "sales", "sale", "last", "month", "months", "year", "years", "in",
        "and", "or", "all", "useful", "data", "details", "record", "records",
        "please", "customer", "lead", "vehicle", "vehicles", "car", "cars",
        "stock", "inventory", "status",
    }
    return [
        token for token in re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
        if len(token) >= 2 and token not in stop
    ][:12]


def _ultra_extract_name(query_text: str) -> str | None:
    q = str(query_text or "").strip()

    patterns = [
        r"(?:phone number|contact number|mobile number|mobile no|phone no|email|mail|join|joined|customer since|details)\s+(?:of|for)\s+(.+)$",
        r"(?:when did|when was)\s+(.+?)\s+(?:join|joined|created|added)",
        r"(?:what is|what's|show|tell me|get)\s+(?:the\s+)?(?:phone number|contact number|mobile number|email|mail|details)\s+(?:of|for)\s+(.+)$",
        r"(?:of|for)\s+([A-Za-z][A-Za-z .'-]{2,})\??$",
    ]

    for pattern in patterns:
        match = re.search(pattern, q, flags=re.I)
        if match:
            name = match.group(1).strip()
            name = re.sub(r"[?.,!]+$", "", name).strip()
            name = re.sub(r"\b(customer|lead|client)\b", "", name, flags=re.I).strip()
            return name or None

    return None


def _ultra_month_limit(query_text: str) -> int | None:
    q = _ultra_lower(query_text)

    m = re.search(r"(?:last|past|previous)\s+(\d+)\s+months?", q)
    if m:
        return int(m.group(1))

    m = re.search(r"(?:last|past|previous)\s+(\d+)\s+years?", q)
    if m:
        return int(m.group(1)) * 12

    if "few months" in q:
        return 3
    if "couple months" in q:
        return 2
    if "several months" in q:
        return 6
    if "last month" in q or "previous month" in q:
        return 1

    return None


def _ultra_date_filter(query_text: str) -> tuple[dict[str, Any], str | None]:
    month_limit = _ultra_month_limit(query_text)
    if month_limit:
        try:
            start, end = _month_window(month_limit)
            if start and end:
                return {"creation": ["between", [start, end]]}, f"last {month_limit} months"
        except Exception:
            pass

    return {}, None


def _ultra_resource_intent(query_text: str, context: str | None = None) -> dict[str, Any]:
    full = f"{context or ''}\n{query_text or ''}"
    q = _ultra_lower(full)

    is_contact = _ultra_has_any(q, ["phone", "mobile", "contact number", "email", "mail"])
    is_join = _ultra_has_any(q, ["join", "joined", "customer since", "created", "added"])
    is_inventory = _ultra_has_any(q, ["inventory", "stock", "available vehicle", "available car", "vehicle stock"])
    is_invoice = _ultra_has_any(q, ["invoice", "payment", "paid", "unpaid", "due"])
    is_sales = _ultra_has_any(q, ["sale", "sales", "sold", "revenue", "income", "bought", "purchased"])
    is_booking = _ultra_has_any(q, ["booking", "booked", "delivery"])
    is_test_drive = _ultra_has_any(q, ["test drive", "testdrive"])
    is_service = _ultra_has_any(q, ["service", "repair", "job", "jobs"])
    is_chart = _ultra_has_any(q, ["chart", "graph", "trend", "dashboard", "widget", "month wise", "month-wise", "over time"])

    if is_contact or is_join:
        resources = ["customers", "leads"]
        mode = "exact_contact_or_join"
    elif is_inventory:
        resources = ["vehicles"]
        mode = "inventory"
    elif is_invoice:
        resources = ["invoices", "customers", "sales"]
        mode = "invoice"
    elif is_sales:
        resources = ["sales", "invoices", "customers"]
        mode = "sales"
    elif is_booking:
        resources = ["bookings", "customers"]
        mode = "booking"
    elif is_test_drive:
        resources = ["test_drives", "customers", "leads"]
        mode = "test_drive"
    elif is_service:
        resources = ["service_jobs", "customers"]
        mode = "service"
    elif is_chart:
        resources = ["sales", "invoices", "leads", "bookings", "test_drives", "service_jobs", "vehicles"]
        mode = "chart"
    else:
        resources = ["customers", "leads", "sales", "invoices", "vehicles"]
        mode = "general"

    return {
        "mode": mode,
        "resources": resources,
        "name": _ultra_extract_name(query_text) or _ultra_extract_name(full),
        "tokens": _ultra_tokens(query_text),
        "companies": _data_agent_company_mentions(full) if "_data_agent_company_mentions" in globals() else [],
        "is_chart": is_chart,
        "is_contact": is_contact,
        "is_join": is_join,
        "is_sales": is_sales,
        "is_inventory": is_inventory,
        "is_invoice": is_invoice,
    }


def _ultra_fields(resource: str, doctype: str) -> list[str]:
    wanted = {
        "customers": ["name", "creation", "company_id", "company_name", "customer_name", "customer_type", "mobile_no", "email", "status"],
        "leads": ["name", "creation", "company_id", "company_name", "lead_name", "mobile_no", "email", "status", "source", "vehicle_interest"],
        "sales": ["name", "creation", "company_id", "company_name", "customer_name", "model", "variant", "final_price", "status", "invoice_no"],
        "invoices": ["name", "creation", "company_id", "company_name", "customer_name", "invoice_no", "invoice_type", "total_amount", "payment_status", "status", "due_date"],
        "bookings": ["name", "creation", "company_id", "company_name", "customer_name", "model", "variant", "booking_amount", "booking_date", "expected_delivery", "status"],
        "test_drives": ["name", "creation", "company_id", "company_name", "contact_name", "customer_name", "mobile_no", "email", "model", "scheduled_date", "scheduled_time", "status"],
        "service_jobs": ["name", "creation", "company_id", "company_name", "customer_name", "vehicle_reg_no", "model", "service_type", "total_amount", "status"],
        "vehicles": ["name", "creation", "company_id", "company_name", "vehicle_name", "model", "variant", "color", "stock_status", "status"],
    }.get(resource, ["name", "creation", "company_id", "company_name", "status"])

    fields = []
    for field in wanted:
        try:
            if _data_agent_has_field(doctype, field):
                fields.append(field)
        except Exception:
            pass

    return fields or ["name", "creation"]


def _ultra_fetch(resource: str, doctype: str, query_text: str, intent: dict[str, Any]) -> list[dict[str, Any]]:
    fields = _ultra_fields(resource, doctype)
    filters = _data_agent_filters_for_doctype(doctype)
    if filters is None:
        return []

    filters = dict(filters)

    date_filter, _time_text = _ultra_date_filter(query_text)
    if date_filter and resource in {"sales", "invoices", "bookings", "test_drives", "service_jobs"}:
        filters.update(date_filter)

    fetch_limit = ULTRA_RAG_CHART_ROW_LIMIT if intent.get("is_chart") else 500

    try:
        rows = frappe.get_all(
            doctype,
            filters=filters,
            fields=fields,
            order_by="creation desc",
            limit_page_length=fetch_limit,
        )
    except Exception:
        return []

    cleaned = []
    for row in rows:
        item = {}
        for key, value in dict(row).items():
            item[key] = _data_agent_clean_value(value)

        if item.get("company_id") and not item.get("company_name"):
            item["company_name"] = _data_agent_company_name(item.get("company_id"))

        item["_resource"] = resource
        item["_doctype"] = doctype
        cleaned.append(item)

    return cleaned


def _ultra_text(row: dict[str, Any]) -> str:
    return " ".join(str(v or "") for v in row.values()).lower()


def _ultra_rank(rows: list[dict[str, Any]], intent: dict[str, Any]) -> list[dict[str, Any]]:
    name_tokens = _ultra_tokens(intent.get("name"))
    query_tokens = intent.get("tokens") or []
    companies = [str(c).lower() for c in intent.get("companies") or []]

    scored = []
    for idx, row in enumerate(rows):
        text = _ultra_text(row)
        resource = row.get("_resource")
        score = 0

        if name_tokens:
            if all(token in text for token in name_tokens):
                score += 1000
            else:
                for token in name_tokens:
                    if token in text:
                        score += 160

        for token in query_tokens:
            if token in text:
                score += 30

        row_company = str(row.get("company_name") or row.get("company_id") or "").lower()
        for company in companies:
            if company == row_company:
                score += 220
            elif company in row_company:
                score += 120

        if resource == "customers" and (intent.get("is_contact") or intent.get("is_join")):
            score += 300
        if resource == "leads" and intent.get("is_contact"):
            score += 180
        if resource == "sales" and intent.get("is_sales"):
            score += 220
        if resource == "vehicles" and intent.get("is_inventory"):
            score += 220
        if resource == "invoices" and intent.get("is_invoice"):
            score += 220

        scored.append((score, -idx, row))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # For exact contact/date lookup, never send random unrelated rows if no match.
    if intent.get("mode") == "exact_contact_or_join":
        matched = [row for score, _idx, row in scored if score > 0]
        return matched

    return [row for _score, _idx, row in scored]


def _ultra_amount(row: dict[str, Any]) -> float:
    for field in ["final_price", "total_amount", "booking_amount"]:
        try:
            if row.get(field) not in (None, ""):
                return float(row.get(field) or 0)
        except Exception:
            pass
    return 0.0


def _ultra_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_company_count = {}
    by_company_amount = {}
    by_status_count = {}
    by_month_count = {}
    by_month_amount = {}

    for row in rows:
        company = str(row.get("company_name") or row.get("company_id") or "Unknown")
        status = str(row.get("status") or row.get("payment_status") or row.get("stock_status") or "Unknown")
        month = str(row.get("creation") or "Unknown")[:7]
        amount = _ultra_amount(row)

        by_company_count[company] = by_company_count.get(company, 0) + 1
        by_company_amount[company] = by_company_amount.get(company, 0.0) + amount
        by_status_count[status] = by_status_count.get(status, 0) + 1
        by_month_count[month] = by_month_count.get(month, 0) + 1
        by_month_amount[month] = by_month_amount.get(month, 0.0) + amount

    return {
        "total_rows_available": len(rows),
        "by_company_count": dict(sorted(by_company_count.items())),
        "by_company_amount": dict(sorted(by_company_amount.items())),
        "by_status_count": dict(sorted(by_status_count.items())),
        "by_month_count": dict(sorted(by_month_count.items())),
        "by_month_amount": dict(sorted(by_month_amount.items())),
    }


def _ultra_build_pack(user_query: str, conversation_context: str | None = None) -> dict[str, Any]:
    is_admin, company_id, company_name = _data_agent_current_scope()
    catalog = _data_agent_catalog()
    intent = _ultra_resource_intent(user_query, conversation_context)

    resources = {}

    for resource in intent["resources"]:
        meta = catalog.get(resource)
        if not meta:
            continue

        doctype = meta["doctype"]
        all_rows = _ultra_fetch(resource, doctype, user_query, intent)
        ranked = _ultra_rank(all_rows, intent)

        if intent["mode"] == "exact_contact_or_join":
            keep = ULTRA_RAG_DETAIL_LIMIT
        elif intent["is_chart"]:
            keep = 10
        elif intent["mode"] in {"inventory", "sales", "invoice"}:
            keep = 40
        else:
            keep = 30

        rows_for_llm = ranked[:keep]

        resources[resource] = {
            "doctype": doctype,
            "title": meta["title"],
            "fields": _ultra_fields(resource, doctype),
            "row_count": len(rows_for_llm),
            "total_rows_available": len(all_rows),
            "summary": _ultra_summary(all_rows),
            "rows": rows_for_llm,
        }

    pack = {
        "scope": {
            "is_admin": is_admin,
            "company_id": company_id,
            "company_name": company_name,
            "access_note": "Admin can see all companies." if is_admin else f"Tenant user can see only {company_name}.",
        },
        "retrieval": {
            "mode": "ultra_compact_structured_rag",
            "intent": intent,
            "note": "Only top ranked authorised rows and compact summaries are sent to GPT.",
        },
        "resources": resources,
        "widget_policy": {
            "record_table": "Use only for useful lists/details.",
            "generic_charts": "Use only for useful trends/comparisons/status breakdowns.",
            "no_widget": "Use for single direct answers.",
        },
    }

    pack["_debug_context_chars"] = len(json.dumps(pack, ensure_ascii=False, default=str, separators=(",", ":")))
    return pack


def _data_agent_prompt(user_query: str, conversation_context: str | None, data_pack: dict[str, Any]) -> str:
    compact_pack = json.dumps(data_pack, ensure_ascii=False, default=str, separators=(",", ":"))

    return f"""You are Vividity, a DMS data agent.

Answer only from the authorised DMS data pack. Do not invent values.
If the answer is not present, say the matching data was not found.

Rules:
- For phone/email/date questions, answer directly and do not use widgets.
- For join/customer-since questions, use a join field if present; otherwise use creation.
- For list/detail questions, use record_table only if useful.
- For trends/comparisons/status breakdowns, use generic_charts only if useful.
- Sales/sold/cars sold normally means vehicle sale count unless revenue/amount/income is explicit.

User question:
{user_query}

Conversation context:
{conversation_context or ""}

Authorised DMS data pack:
{compact_pack}
""".strip()


@frappe.whitelist(allow_guest=True)
def query(query: str | None = None, conversation_context: str | None = None, **kwargs):
    provider, _api_key, _model = _data_agent_provider_config()

    if provider != "openai":
        previous = globals().get("_OPENAI_DATA_AGENT_PREVIOUS_QUERY")
        if callable(previous):
            try:
                return previous(query=query, conversation_context=conversation_context, **kwargs)
            except TypeError:
                return previous()
        return success(data=_final_out_of_scope_response())

    payload = _data_agent_request_payload()
    payload.update(kwargs or {})

    user_query = str(query or payload.get("query") or payload.get("message") or payload.get("text") or "").strip()
    conversation_context = str(conversation_context or payload.get("conversation_context") or payload.get("context") or "")

    if not user_query:
        data = _base_response(
            intent="out_of_scope",
            metric=None,
            time_range=None,
            company_id=None,
            company_name=None,
            widgets_to_show=[],
            text_response="Please ask a DMS data question.",
            widget_payloads={},
            other={"answer_type": "empty_query"},
        )
        return success(data=data)

    denial = _data_agent_cross_tenant_denial(user_query)
    if denial:
        return success(data=denial)

    data_pack = _ultra_build_pack(user_query, conversation_context)
    plan = _data_agent_call_openai(user_query, conversation_context, data_pack)

    if plan.get("_llm_status") != "ok":
        data = _data_agent_llm_error(plan, user_query)
        try:
            data["filters_applied"]["other"]["rag_mode"] = "ultra_compact_structured_rag"
            data["filters_applied"]["other"]["rag_context_chars"] = data_pack.get("_debug_context_chars")
            data["filters_applied"]["other"]["rag_resources"] = list((data_pack.get("resources") or {}).keys())
        except Exception:
            pass
        return success(data=data)

    data = _data_agent_response(plan, data_pack, user_query)

    try:
        data["filters_applied"]["other"]["rag_mode"] = "ultra_compact_structured_rag"
        data["filters_applied"]["other"]["rag_context_chars"] = data_pack.get("_debug_context_chars")
        data["filters_applied"]["other"]["rag_resources"] = list((data_pack.get("resources") or {}).keys())
    except Exception:
        pass

    return success(data=data)

# ULTRA_COMPACT_RAG_FINAL_PATCH_END

