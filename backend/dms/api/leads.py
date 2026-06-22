"""
Leads CRUD API.

GET    /api/method/dms.api.leads.get_leads
POST   /api/method/dms.api.leads.create_lead
PUT    /api/method/dms.api.leads.update_lead
DELETE /api/method/dms.api.leads.delete_lead
POST   /api/method/dms.api.leads.convert_to_customer
"""

import frappe
from frappe import _
from dms.utils.permissions import get_user_company, is_group_admin, require_company_access
from dms.utils.response import success, error, paginated

DOCTYPE = "DMS Lead"

ALLOWED_STATUSES = ["New", "Open", "Replied", "Opportunity", "Quotation", "Converted", "Do Not Contact", "Lost"]
ALLOWED_SOURCES = ["Website", "Cold Calling", "Referral", "Social Media", "Walk-in", "Exhibition", "Campaign", "Digital"]


@frappe.whitelist()
def get_leads(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    source: str = None,
    search: str = None,
    date_from: str = None,
    date_to: str = None,
    assigned_to: str = None,
):
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    filters = _build_filters(status, source, search, date_from, date_to, assigned_to)

    docs = frappe.get_all(
        DOCTYPE,
        filters=filters,
        fields=[
            "name as id", "lead_name", "email", "mobile_no", "status",
            "source", "company_id", "company_name", "vehicle_interest",
            "budget", "notes", "assigned_to", "follow_up_date",
            "creation as created_at", "modified as modified_at",
        ],
        start=offset,
        page_length=page_size,
        order_by="creation desc",
    )

    total = frappe.db.count(DOCTYPE, filters=filters)
    return paginated(docs, total, page, page_size)


@frappe.whitelist()
def get_lead(lead_id: str):
    doc = frappe.get_doc(DOCTYPE, lead_id)
    require_company_access(doc.company_id)
    return success(data=doc.as_dict())


@frappe.whitelist()
def create_lead(
    lead_name: str,
    email: str,
    mobile_no: str,
    status: str = "New",
    source: str = "Walk-in",
    vehicle_interest: str = None,
    budget: float = None,
    notes: str = None,
):
    _validate_status(status)
    _validate_source(source)

    company_id = get_user_company()
    if not company_id:
        return error(_("Group Admin must specify a company_id."), 400)

    company_name = frappe.db.get_value("DMS Company", company_id, "company_name") or company_id

    doc = frappe.new_doc(DOCTYPE)
    doc.update({
        "lead_name": lead_name,
        "email": email,
        "mobile_no": mobile_no,
        "status": status,
        "source": source,
        "company_id": company_id,
        "company_name": company_name,
        "vehicle_interest": vehicle_interest,
        "budget": budget,
        "notes": notes,
        "assigned_to": frappe.session.user,
    })
    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    return success(data=doc.as_dict(), http_status_code=201)


@frappe.whitelist()
def update_lead(lead_id: str, **kwargs):
    doc = frappe.get_doc(DOCTYPE, lead_id)
    require_company_access(doc.company_id)

    allowed_fields = ["lead_name", "email", "mobile_no", "status", "source",
                      "vehicle_interest", "budget", "notes", "assigned_to", "follow_up_date"]
    for field in allowed_fields:
        if field in kwargs:
            setattr(doc, field, kwargs[field])

    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return success(data=doc.as_dict())


@frappe.whitelist()
def delete_lead(lead_id: str):
    doc = frappe.get_doc(DOCTYPE, lead_id)
    require_company_access(doc.company_id)
    doc.delete()
    frappe.db.commit()
    return success(message="Lead deleted successfully")


@frappe.whitelist()
def convert_to_customer(lead_id: str):
    lead = frappe.get_doc(DOCTYPE, lead_id)
    require_company_access(lead.company_id)

    if lead.status == "Converted":
        return error(_("Lead is already converted."), 400)

    customer = frappe.new_doc("DMS Customer")
    customer.update({
        "customer_name": lead.lead_name,
        "email": lead.email,
        "mobile_no": lead.mobile_no,
        "company_id": lead.company_id,
        "company_name": lead.company_name,
        "customer_type": "Individual",
        "status": "Active",
    })
    customer.insert(ignore_permissions=False)

    lead.status = "Converted"
    lead.save(ignore_permissions=False)
    frappe.db.commit()

    return success(data={"customer_id": customer.name}, message="Lead converted to customer")


def _build_filters(status, source, search, date_from, date_to, assigned_to):
    filters = {}

    if not is_group_admin():
        company_id = get_user_company()
        if company_id and company_id != "__none__":
            filters["company_id"] = company_id

    if status:
        filters["status"] = status
    if source:
        filters["source"] = source
    if assigned_to:
        filters["assigned_to"] = assigned_to

    if search:
        filters[["lead_name", "like", f"%{search}%"]] = None  # type: ignore
        # Frappe OR filters use list syntax; simplified here
        # In production use frappe.db.sql with OR

    return filters


def _validate_status(status: str):
    if status not in ALLOWED_STATUSES:
        frappe.throw(_(f"Invalid status: {status}"), frappe.ValidationError)


def _validate_source(source: str):
    if source not in ALLOWED_SOURCES:
        frappe.throw(_(f"Invalid source: {source}"), frappe.ValidationError)
