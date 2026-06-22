from frappe import _

app_name = "dms"
app_title = "Dealer Management System"
app_publisher = "DMS Group"
app_description = "Enterprise Dealer Management System for multi-brand automotive dealer groups"
app_version = "1.0.0"
app_email = "admin@dmsgroup.com"
app_license = "MIT"

# DocType permissions
# Each DocType has company_id field used for row-level security

fixtures = [
    {
        "dt": "Role",
        "filters": [
            ["name", "in", [
                "Honda User", "Honda Manager",
                "NEXA User", "NEXA Manager",
                "Jaguar User", "Jaguar Manager",
                "Group Admin",
            ]]
        ],
    },
    {
        "dt": "Custom Field",
        "filters": [["dt", "in", ["User"]]],
    },
]

# Override standard Frappe doctypes
override_doctype_dashboards = {}

# API whitelist — all dms.api.* are whitelisted via @frappe.whitelist decorator

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "dms.tasks.daily.send_follow_up_reminders",
        "dms.tasks.daily.update_lead_scores",
    ],
    "weekly": [
        "dms.tasks.weekly.generate_weekly_report",
    ],
}

# Website
# website_route_rules = []

# Authentication
auth_hooks = [
    "dms.api.auth.authenticate_jwt"
]

# Boot session
boot_session = "dms.boot.boot_session"

# Permission Query Conditions
permission_query_conditions = {
    "DMS Lead":        "dms.utils.permissions.get_permission_query_conditions",
    "DMS Customer":    "dms.utils.permissions.get_permission_query_conditions",
    "DMS Vehicle":     "dms.utils.permissions.get_permission_query_conditions",
    "DMS Vehicle Sale":"dms.utils.permissions.get_permission_query_conditions",
    "DMS Booking":     "dms.utils.permissions.get_permission_query_conditions",
    "DMS Test Drive":  "dms.utils.permissions.get_permission_query_conditions",
    "DMS Service Job": "dms.utils.permissions.get_permission_query_conditions",
    "DMS Invoice":     "dms.utils.permissions.get_permission_query_conditions",
}

has_permission = {
    "DMS Lead":         "dms.utils.permissions.has_permission",
    "DMS Customer":     "dms.utils.permissions.has_permission",
    "DMS Vehicle":      "dms.utils.permissions.has_permission",
    "DMS Vehicle Sale": "dms.utils.permissions.has_permission",
    "DMS Booking":      "dms.utils.permissions.has_permission",
    "DMS Test Drive":   "dms.utils.permissions.has_permission",
    "DMS Service Job":  "dms.utils.permissions.has_permission",
    "DMS Invoice":      "dms.utils.permissions.has_permission",
}
