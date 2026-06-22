import re

from app.core.auth_context import AuthContext, UserRole
from app.repositories.mock_erp_repository import (
    list_inventory_records,
    list_sales_records,
)
from app.schemas.agent_schema import AgentQueryResponse, FiltersApplied
from app.services.widget_registry import get_all_widget_ids, get_hidden_widgets


KNOWN_TENANTS = ["toyota", "suzuki", "hyundai"]


def detect_intent(query: str) -> str:
    q = query.lower()

    if any(word in q for word in ["sales", "revenue", "income"]):
        return "sales_analysis"

    if any(word in q for word in ["service", "servicing", "appointment", "job"]):
        return "service_analysis"

    if any(word in q for word in ["inventory", "stock", "parts", "spares"]):
        return "inventory_analysis"

    if any(word in q for word in ["compare", "comparison", "across tenants"]):
        return "tenant_comparison"

    return "out_of_scope"


def extract_month_limit(query: str) -> int | None:
    match = re.search(r"last\s+(\d+)\s+months?", query.lower())

    if not match:
        return None

    month_limit = int(match.group(1))

    if month_limit <= 0:
        return None

    return min(month_limit, 24)


def resolve_tenant_scope(
    query: str,
    auth_context: AuthContext,
) -> str | None:
    """
    Critical rule:
    Tenant users cannot override tenant scope through natural language.
    """

    if auth_context.user_role == UserRole.TENANT_USER:
        return auth_context.tenant_id

    q = query.lower()

    for tenant_id in KNOWN_TENANTS:
        if tenant_id in q:
            return tenant_id

    return None


def build_sales_response(
    query: str,
    auth_context: AuthContext,
) -> AgentQueryResponse:
    month_limit = extract_month_limit(query)
    tenant_scope = resolve_tenant_scope(query, auth_context)

    records = list_sales_records(
        tenant_id=tenant_scope,
        month_limit=month_limit,
    )

    visible_widgets = ["sales_chart"]

    if not records:
        return AgentQueryResponse(
            intent="sales_analysis",
            filters_applied=FiltersApplied(
                metric="sales",
                time_range=f"last {month_limit} months" if month_limit else "all_available",
                tenant_id=tenant_scope or "all_allowed_tenants",
                other=None,
            ),
            widgets_to_show=visible_widgets,
            widgets_to_hide=get_hidden_widgets(visible_widgets),
            text_response="No sales data was found for the selected scope.",
            widget_payloads={
                "sales_chart": {
                    "labels": [],
                    "series": []
                }
            }
        )

    total_sales = sum(row["sales"] for row in records)
    highest_month = max(records, key=lambda row: row["sales"])

    labels = [row["month"] for row in records]
    series = [row["sales"] for row in records]

    tenant_text = tenant_scope.title() if tenant_scope else "all allowed tenants"
    time_text = f"the last {month_limit} months" if month_limit else "all available months"

    return AgentQueryResponse(
        intent="sales_analysis",
        filters_applied=FiltersApplied(
            metric="sales",
            time_range=time_text,
            tenant_id=tenant_scope or "all_allowed_tenants",
            other=None,
        ),
        widgets_to_show=visible_widgets,
        widgets_to_hide=get_hidden_widgets(visible_widgets),
        text_response=(
            f"Total sales for {tenant_text} over {time_text} were ₹{total_sales:,}. "
            f"The highest month was {highest_month['month']} with ₹{highest_month['sales']:,}."
        ),
        widget_payloads={
            "sales_chart": {
                "labels": labels,
                "series": series,
                "total": total_sales,
                "highest_month": highest_month,
            }
        }
    )


def build_service_response(
    query: str,
    auth_context: AuthContext,
) -> AgentQueryResponse:
    month_limit = extract_month_limit(query)
    tenant_scope = resolve_tenant_scope(query, auth_context)

    records = list_sales_records(
        tenant_id=tenant_scope,
        month_limit=month_limit,
    )

    visible_widgets = ["service_count_chart"]

    labels = [row["month"] for row in records]
    series = [row["service_count"] for row in records]
    total_services = sum(series)

    tenant_text = tenant_scope.title() if tenant_scope else "all allowed tenants"

    return AgentQueryResponse(
        intent="service_analysis",
        filters_applied=FiltersApplied(
            metric="service_count",
            time_range=f"last {month_limit} months" if month_limit else "all_available",
            tenant_id=tenant_scope or "all_allowed_tenants",
            other=None,
        ),
        widgets_to_show=visible_widgets,
        widgets_to_hide=get_hidden_widgets(visible_widgets),
        text_response=(
            f"Total service records for {tenant_text} were {total_services:,}."
        ),
        widget_payloads={
            "service_count_chart": {
                "labels": labels,
                "series": series,
                "total": total_services,
            }
        }
    )


def build_inventory_response(
    query: str,
    auth_context: AuthContext,
) -> AgentQueryResponse:
    tenant_scope = resolve_tenant_scope(query, auth_context)

    records = list_inventory_records(tenant_id=tenant_scope)

    visible_widgets = ["inventory_table"]

    total_stock = sum(row["stock"] for row in records)
    low_stock_items = [
        row for row in records
        if row["stock"] < 100
    ]

    tenant_text = tenant_scope.title() if tenant_scope else "all allowed tenants"

    return AgentQueryResponse(
        intent="inventory_analysis",
        filters_applied=FiltersApplied(
            metric="stock",
            time_range="current",
            tenant_id=tenant_scope or "all_allowed_tenants",
            other={
                "low_stock_threshold": 100
            },
        ),
        widgets_to_show=visible_widgets,
        widgets_to_hide=get_hidden_widgets(visible_widgets),
        text_response=(
            f"Current inventory stock for {tenant_text} is {total_stock:,} units. "
            f"{len(low_stock_items)} item category/categories are below the low-stock threshold."
        ),
        widget_payloads={
            "inventory_table": {
                "rows": records,
                "total_stock": total_stock,
                "low_stock_items": low_stock_items,
            }
        }
    )


def build_tenant_comparison_response(
    query: str,
    auth_context: AuthContext,
) -> AgentQueryResponse:
    if auth_context.user_role != UserRole.SERVICE_CENTRE_ADMIN:
        return AgentQueryResponse(
            intent="unauthorized",
            filters_applied=FiltersApplied(
                metric=None,
                time_range=None,
                tenant_id=auth_context.tenant_id,
                other=None,
            ),
            widgets_to_show=[],
            widgets_to_hide=get_all_widget_ids(),
            text_response="You do not have permission to access cross-tenant comparison data.",
            widget_payloads={}
        )

    month_limit = extract_month_limit(query)
    records = list_sales_records(month_limit=month_limit)

    tenant_totals: dict[str, int] = {}

    for row in records:
        tenant_totals[row["tenant_id"]] = tenant_totals.get(row["tenant_id"], 0) + row["sales"]

    visible_widgets = ["tenant_comparison_chart"]

    return AgentQueryResponse(
        intent="tenant_comparison",
        filters_applied=FiltersApplied(
            metric="sales",
            time_range=f"last {month_limit} months" if month_limit else "all_available",
            tenant_id="all_allowed_tenants",
            other=None,
        ),
        widgets_to_show=visible_widgets,
        widgets_to_hide=get_hidden_widgets(visible_widgets),
        text_response="Tenant comparison has been prepared for all allowed tenants.",
        widget_payloads={
            "tenant_comparison_chart": {
                "labels": list(tenant_totals.keys()),
                "series": list(tenant_totals.values()),
            }
        }
    )


def run_dashboard_agent(
    query: str,
    auth_context: AuthContext,
) -> AgentQueryResponse:
    intent = detect_intent(query)

    if intent == "sales_analysis":
        return build_sales_response(query, auth_context)

    if intent == "service_analysis":
        return build_service_response(query, auth_context)

    if intent == "inventory_analysis":
        return build_inventory_response(query, auth_context)

    if intent == "tenant_comparison":
        return build_tenant_comparison_response(query, auth_context)

    return AgentQueryResponse(
        intent="out_of_scope",
        filters_applied=FiltersApplied(
            metric=None,
            time_range=None,
            tenant_id=auth_context.tenant_id or "all_allowed_tenants",
            other=None,
        ),
        widgets_to_show=[],
        widgets_to_hide=get_all_widget_ids(),
        text_response=(
            "I can only assist with ERP dashboard queries such as sales, "
            "service records, inventory, and tenant performance."
        ),
        widget_payloads={}
    )
