import frappe
from frappe import _

GROUP_ADMIN_ROLE = "Group Admin"
COMPANY_ROLES = {
    "Honda":  ["Honda User", "Honda Manager"],
    "NEXA":   ["NEXA User", "NEXA Manager"],
    "Jaguar": ["Jaguar User", "Jaguar Manager"],
}


def get_user_company() -> str | None:
    """Return the company_id the current user belongs to, or None for Group Admin."""
    user_roles = frappe.get_roles(frappe.session.user)

    if GROUP_ADMIN_ROLE in user_roles:
        return None  # sees all data

    for company, roles in COMPANY_ROLES.items():
        if any(role in user_roles for role in roles):
            # Resolve company_id from DMS Company doctype
            company_doc = frappe.db.get_value(
                "DMS Company", {"company_name": company}, "name"
            )
            return company_doc

    return "__none__"  # unknown role → see nothing


def is_group_admin() -> bool:
    return GROUP_ADMIN_ROLE in frappe.get_roles(frappe.session.user)


def get_permission_query_conditions(user: str = None) -> str:
    if not user:
        user = frappe.session.user

    if GROUP_ADMIN_ROLE in frappe.get_roles(user):
        return ""  # no restriction

    company_id = get_user_company()
    if not company_id or company_id == "__none__":
        return "(`tabDMS Lead`.`company_id` = '__none__')"

    return f"(`tabDMS Lead`.`company_id` = {frappe.db.escape(company_id)})"


def has_permission(doc, ptype="read", user=None) -> bool:
    if not user:
        user = frappe.session.user

    if GROUP_ADMIN_ROLE in frappe.get_roles(user):
        return True

    company_id = get_user_company()
    if not company_id or company_id == "__none__":
        return False

    return getattr(doc, "company_id", None) == company_id


def require_company_access(company_id: str):
    """Raise PermissionError if the current user cannot access data for company_id."""
    if is_group_admin():
        return
    user_company = get_user_company()
    if user_company != company_id:
        frappe.throw(
            _("You do not have permission to access data for this company."),
            frappe.PermissionError,
        )
