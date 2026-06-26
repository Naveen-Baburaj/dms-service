from __future__ import annotations

import frappe


def boot_session(bootinfo):
    """Add DMS-specific boot metadata for Frappe Desk.

    Frappe calls this during Desk startup because hooks.py defines:
    boot_session = "dms.boot.boot_session"

    Keep this lightweight. Do not run expensive queries here.
    """

    roles = frappe.get_roles(frappe.session.user)

    bootinfo.dms = {
        "app_name": "dms",
        "app_title": "Dealer Management System",
        "user": frappe.session.user,
        "roles": roles,
        "is_group_admin": "Group Admin" in roles or frappe.session.user == "Administrator",
    }

    return bootinfo
