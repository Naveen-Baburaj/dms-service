import frappe


def generate_weekly_report():
    """Placeholder weekly task for generating dealer performance reports.

    This keeps the scheduler hook valid during the demo.
    The real implementation can later aggregate weekly sales, leads,
    service jobs, bookings, and company-wise KPIs.
    """
    frappe.logger("dms").info("DMS weekly task executed: generate_weekly_report")
    return {
        "status": "skipped",
        "message": "Weekly report automation is not implemented yet.",
    }
