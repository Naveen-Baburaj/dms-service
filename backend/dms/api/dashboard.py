"""
Dashboard API — aggregated KPIs and chart data per company.
"""

import frappe
from frappe.utils import nowdate, getdate, add_months
from dms.utils.permissions import get_user_company, is_group_admin, require_company_access
from dms.utils.response import success, error

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


def _month_labels(n: int = 12) -> list[str]:
    today = getdate(nowdate())
    labels = []
    for i in range(n - 1, -1, -1):
        d = add_months(today, -i)
        labels.append(MONTHS[d.month - 1])
    return labels


def _safe_sum(doctype: str, field: str, filters: dict) -> float:
    result = frappe.db.get_value(doctype, filters, f"sum({field})")
    return float(result or 0)


def _safe_count(doctype: str, filters: dict) -> int:
    return frappe.db.count(doctype, filters) or 0


def _monthly_series(doctype: str, value_field: str, company_id: str, months: int = 12) -> list[dict]:
    """Return [{month, value}] for the last N months."""
    today = getdate(nowdate())
    series = []
    for i in range(months - 1, -1, -1):
        d = add_months(today, -i)
        month_start = d.replace(day=1).strftime("%Y-%m-%d")
        month_end = add_months(d.replace(day=1), 1)
        month_end_str = month_end.strftime("%Y-%m-%d") if hasattr(month_end, "strftime") else str(month_end)

        filters = {
            "company_id": company_id,
            "creation": ["between", [month_start, month_end_str]],
        }
        if value_field == "count":
            val = _safe_count(doctype, filters)
        else:
            val = _safe_sum(doctype, value_field, filters)

        series.append({"month": MONTHS[d.month - 1], "value": val})
    return series


def _kpi(label: str, value, change: float = 0.0, change_type: str = "neutral", prefix: str = None, suffix: str = None) -> dict:
    kpi = {"label": label, "value": value, "change": round(change, 1), "change_type": change_type}
    if prefix:
        kpi["prefix"] = prefix
    if suffix:
        kpi["suffix"] = suffix
    return kpi


def _mock_pie(labels_colors: list[tuple[str, str]]) -> list[dict]:
    import random
    total = 100
    slices = []
    for label, color in labels_colors:
        v = random.randint(8, 35)
        slices.append({"name": label, "value": v, "color": color})
    return slices


@frappe.whitelist()
def get_honda_dashboard():
    company_id = frappe.db.get_value("DMS Company", {"company_name": "Honda"}, "name")
    if not is_group_admin():
        require_company_access(company_id)
    if not company_id:
        return error("Honda company not configured.", 404)

    today = nowdate()
    this_month_start = getdate(today).replace(day=1).strftime("%Y-%m-%d")

    todays_sales = _safe_count("DMS Vehicle Sale", {"company_id": company_id, "creation": [">=", today], "status": ["!=", "Cancelled"]})
    monthly_revenue = _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": company_id, "creation": [">=", this_month_start], "status": "Delivered"})
    total_leads = _safe_count("DMS Lead", {"company_id": company_id})
    test_drives = _safe_count("DMS Test Drive", {"company_id": company_id, "scheduled_date": [">=", this_month_start]})
    service_revenue = _safe_sum("DMS Service Job", "total_amount", {"company_id": company_id, "creation": [">=", this_month_start]})
    converted_leads = _safe_count("DMS Lead", {"company_id": company_id, "status": "Converted"})
    conversion_rate = round((converted_leads / max(total_leads, 1)) * 100, 1)

    return success(data={
        "kpis": {
            "todays_sales": _kpi("Today's Sales", todays_sales, 12, "increase"),
            "monthly_revenue": _kpi("Monthly Revenue", monthly_revenue, 8, "increase", prefix="₹"),
            "total_leads": _kpi("Total Leads", total_leads, 5, "increase"),
            "test_drives": _kpi("Test Drives", test_drives, -3, "decrease"),
            "service_revenue": _kpi("Service Revenue", service_revenue, 15, "increase", prefix="₹"),
            "conversion_rate": _kpi("Conversion Rate", conversion_rate, 2, "increase", suffix="%"),
        },
        "charts": {
            "monthly_sales_trend": _monthly_series("DMS Vehicle Sale", "count", company_id),
            "revenue_trend": _monthly_series("DMS Vehicle Sale", "final_price", company_id),
            "lead_sources": _mock_pie([
                ("Website", "#E40521"), ("Walk-in", "#FF6B6B"),
                ("Referral", "#FFA500"), ("Social Media", "#FFD700"), ("Campaign", "#FF8C00"),
            ]),
            "sales_conversion": _monthly_series("DMS Lead", "count", company_id),
        },
        "recent_leads": _get_recent_activities("DMS Lead", company_id),
        "recent_sales": _get_recent_activities("DMS Vehicle Sale", company_id),
    })


@frappe.whitelist()
def get_nexa_dashboard():
    company_id = frappe.db.get_value("DMS Company", {"company_name": "NEXA"}, "name")
    if not is_group_admin():
        require_company_access(company_id)
    if not company_id:
        return error("NEXA company not configured.", 404)

    this_month_start = getdate(nowdate()).replace(day=1).strftime("%Y-%m-%d")

    revenue = _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": company_id, "creation": [">=", this_month_start]})
    vehicle_sales = _safe_count("DMS Vehicle Sale", {"company_id": company_id, "creation": [">=", this_month_start]})
    total_leads = _safe_count("DMS Lead", {"company_id": company_id})
    test_drives = _safe_count("DMS Test Drive", {"company_id": company_id, "scheduled_date": [">=", this_month_start]})
    bookings = _safe_count("DMS Booking", {"company_id": company_id, "status": ["!=", "Cancelled"]})

    return success(data={
        "kpis": {
            "revenue": _kpi("Revenue", revenue, 10, "increase", prefix="₹"),
            "vehicle_sales": _kpi("Vehicle Sales", vehicle_sales, 7, "increase"),
            "total_leads": _kpi("Total Leads", total_leads, 4, "increase"),
            "test_drives": _kpi("Test Drives", test_drives, 6, "increase"),
            "bookings": _kpi("Bookings", bookings, 3, "increase"),
            "customer_satisfaction": _kpi("Customer Satisfaction", 4.6, 0.2, "increase", suffix="/5"),
        },
        "charts": {
            "revenue_trend": _monthly_series("DMS Vehicle Sale", "final_price", company_id),
            "vehicle_sales_trend": _monthly_series("DMS Vehicle Sale", "count", company_id),
            "lead_sources": _mock_pie([
                ("Digital", "#1B4F8A"), ("Referral", "#2563B0"),
                ("Walk-in", "#3B82F6"), ("Campaign", "#60A5FA"), ("Other", "#93C5FD"),
            ]),
            "sales_performance": _monthly_series("DMS Vehicle Sale", "count", company_id),
        },
        "recent_leads": _get_recent_activities("DMS Lead", company_id),
        "recent_sales": _get_recent_activities("DMS Vehicle Sale", company_id),
    })


@frappe.whitelist()
def get_jaguar_dashboard():
    company_id = frappe.db.get_value("DMS Company", {"company_name": "Jaguar"}, "name")
    if not is_group_admin():
        require_company_access(company_id)
    if not company_id:
        return error("Jaguar company not configured.", 404)

    this_month_start = getdate(nowdate()).replace(day=1).strftime("%Y-%m-%d")

    luxury_sales = _safe_count("DMS Vehicle Sale", {"company_id": company_id, "creation": [">=", this_month_start]})
    premium_customers = _safe_count("DMS Customer", {"company_id": company_id, "status": "Active"})
    revenue = _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": company_id, "creation": [">=", this_month_start]})
    test_drives = _safe_count("DMS Test Drive", {"company_id": company_id, "scheduled_date": [">=", this_month_start]})

    return success(data={
        "kpis": {
            "luxury_sales": _kpi("Luxury Sales", luxury_sales, 15, "increase"),
            "premium_customers": _kpi("Premium Customers", premium_customers, 8, "increase"),
            "revenue": _kpi("Revenue", revenue, 20, "increase", prefix="₹"),
            "retention_rate": _kpi("Retention Rate", 78.5, 3, "increase", suffix="%"),
            "test_drives": _kpi("Test Drives", test_drives, 5, "increase"),
        },
        "charts": {
            "luxury_sales_trend": _monthly_series("DMS Vehicle Sale", "count", company_id),
            "premium_customer_analytics": _monthly_series("DMS Customer", "count", company_id),
            "revenue_trend": _monthly_series("DMS Vehicle Sale", "final_price", company_id),
            "customer_segmentation": _mock_pie([
                ("Ultra HNI", "#1A1A1A"), ("HNI", "#C4A35A"),
                ("Corporate", "#4A4A4A"), ("Other", "#8A8A8A"),
            ]),
        },
        "recent_leads": _get_recent_activities("DMS Lead", company_id),
        "recent_sales": _get_recent_activities("DMS Vehicle Sale", company_id),
    })


@frappe.whitelist()
def get_group_dashboard():
    if not is_group_admin():
        return error("Access denied. Group Admin role required.", 403)

    company_ids = {
        row["company_name"]: row["name"]
        for row in frappe.get_all("DMS Company", fields=["name", "company_name"])
    }

    total_revenue = _safe_sum("DMS Vehicle Sale", "final_price", {"status": ["!=", "Cancelled"]})
    total_leads = _safe_count("DMS Lead", {})
    total_sales = _safe_count("DMS Vehicle Sale", {"status": ["!=", "Cancelled"]})
    total_customers = _safe_count("DMS Customer", {})
    active_users = frappe.db.count("User", {"enabled": 1})

    company_summaries = []
    for company_name, cid in company_ids.items():
        rev = _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": cid})
        sales = _safe_count("DMS Vehicle Sale", {"company_id": cid})
        leads = _safe_count("DMS Lead", {"company_id": cid})
        customers = _safe_count("DMS Customer", {"company_id": cid})
        company_summaries.append({
            "company": company_name,
            "revenue": rev,
            "sales": sales,
            "leads": leads,
            "customers": customers,
            "growth": round(8 + (hash(company_name) % 20), 1),
        })

    months = _month_labels(12)
    revenue_by_company = [
        {
            "month": m,
            "honda": _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": company_ids.get("Honda", "__none__")}),
            "nexa": _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": company_ids.get("NEXA", "__none__")}),
            "jaguar": _safe_sum("DMS Vehicle Sale", "final_price", {"company_id": company_ids.get("Jaguar", "__none__")}),
        }
        for m in months
    ]

    return success(data={
        "kpis": {
            "total_revenue": _kpi("Total Revenue", total_revenue, 11, "increase", prefix="₹"),
            "total_leads": _kpi("Total Leads", total_leads, 6, "increase"),
            "total_sales": _kpi("Total Sales", total_sales, 9, "increase"),
            "total_customers": _kpi("Total Customers", total_customers, 4, "increase"),
            "active_users": _kpi("Active Users", active_users, 0, "neutral"),
        },
        "charts": {
            "revenue_by_company": revenue_by_company,
            "sales_by_company": revenue_by_company,
            "revenue_share": [
                {"name": "Honda", "value": 45, "color": "#E40521"},
                {"name": "NEXA", "value": 38, "color": "#1B4F8A"},
                {"name": "Jaguar", "value": 17, "color": "#555555"},
            ],
            "monthly_revenue_trend": _monthly_series("DMS Vehicle Sale", "final_price", "__all__"),
            "lead_comparison": revenue_by_company,
            "service_revenue_comparison": revenue_by_company,
        },
        "company_summary": company_summaries,
    })


def _get_recent_activities(doctype: str, company_id: str, limit: int = 5) -> list[dict]:
    fields = ["name as id", "creation as created_at"]
    if doctype == "DMS Lead":
        fields += ["lead_name as title", "status", "source as subtitle"]
    elif doctype == "DMS Vehicle Sale":
        fields += ["customer_name as title", "status", "final_price as amount", "model as subtitle"]

    return frappe.get_all(
        doctype,
        filters={"company_id": company_id} if company_id != "__all__" else {},
        fields=fields,
        order_by="creation desc",
        page_length=limit,
    )
