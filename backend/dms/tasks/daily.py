import frappe


def send_follow_up_reminders():
    """Placeholder daily task for sending lead/customer follow-up reminders.

    This keeps the scheduler hook valid during the demo.
    The real implementation can later query open leads, overdue test drives,
    pending bookings, or service follow-ups and send notifications.
    """
    frappe.logger("dms").info("DMS daily task executed: send_follow_up_reminders")
    return {
        "status": "skipped",
        "message": "Follow-up reminder automation is not implemented yet.",
    }


def update_lead_scores():
    """Placeholder daily task for refreshing lead scores.

    This keeps the scheduler hook valid during the demo.
    The real implementation can later score leads based on enquiry source,
    budget, preferred model, test-drive activity, and follow-up status.
    """
    frappe.logger("dms").info("DMS daily task executed: update_lead_scores")
    return {
        "status": "skipped",
        "message": "Lead scoring automation is not implemented yet.",
    }
