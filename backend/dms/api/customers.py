"""
Customers API.

GET  /api/method/dms.api.customers.get_customers
POST /api/method/dms.api.customers.create_customer
PUT  /api/method/dms.api.customers.update_customer
GET  /api/method/dms.api.customers.get_purchase_history
"""

import frappe
from frappe import _
from dms.utils.permissions import get_user_company, is_group_admin, require_company_access
from dms.utils.response import success, error, paginated

DOCTYPE = "DMS Customer"


@frappe.whitelist()
def get_customers(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    customer_type: str = None,
    search: str = None,
):
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    filters = {}
    if not is_group_admin():
        company_id = get_user_company()
        if company_id and company_id != "__none__":
            filters["company_id"] = company_id

    if status:
        filters["status"] = status
    if customer_type:
        filters["customer_type"] = customer_type

    docs = frappe.get_all(
        DOCTYPE,
        filters=filters,
        fields=[
            "name as id", "customer_name", "email", "mobile_no",
            "customer_type", "status", "company_id", "company_name",
            "address", "city", "state", "total_purchases",
            "last_purchase_date", "loyalty_points",
            "creation as created_at",
        ],
        start=offset,
        page_length=page_size,
        order_by="creation desc",
    )
    total = frappe.db.count(DOCTYPE, filters=filters)
    return paginated(docs, total, page, page_size)


@frappe.whitelist()
def get_customer(customer_id: str):
    doc = frappe.get_doc(DOCTYPE, customer_id)
    require_company_access(doc.company_id)
    return success(data=doc.as_dict())


@frappe.whitelist()
def create_customer(
    customer_name: str,
    email: str,
    mobile_no: str,
    customer_type: str = "Individual",
    address: str = None,
    city: str = None,
    state: str = None,
    pin_code: str = None,
    dob: str = None,
):
    company_id = get_user_company()
    if not company_id:
        return error(_("Group Admin must specify a company_id."), 400)

    company_name = frappe.db.get_value("DMS Company", company_id, "company_name") or company_id

    if frappe.db.exists(DOCTYPE, {"email": email, "company_id": company_id}):
        return error(_("A customer with this email already exists."), 409)

    doc = frappe.new_doc(DOCTYPE)
    doc.update({
        "customer_name": customer_name,
        "email": email,
        "mobile_no": mobile_no,
        "customer_type": customer_type,
        "company_id": company_id,
        "company_name": company_name,
        "address": address,
        "city": city,
        "state": state,
        "pin_code": pin_code,
        "dob": dob,
        "status": "Active",
        "total_purchases": 0,
        "loyalty_points": 0,
    })
    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    return success(data=doc.as_dict(), http_status_code=201)


@frappe.whitelist()
def update_customer(customer_id: str, **kwargs):
    doc = frappe.get_doc(DOCTYPE, customer_id)
    require_company_access(doc.company_id)

    allowed_fields = [
        "customer_name", "email", "mobile_no", "customer_type",
        "address", "city", "state", "pin_code", "dob", "status",
    ]
    for field in allowed_fields:
        if field in kwargs:
            setattr(doc, field, kwargs[field])

    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return success(data=doc.as_dict())


@frappe.whitelist()
def get_purchase_history(customer_id: str, page: int = 1, page_size: int = 20):
    customer = frappe.get_doc(DOCTYPE, customer_id)
    require_company_access(customer.company_id)

    purchases = frappe.get_all(
        "DMS Vehicle Sale",
        filters={"customer_id": customer_id},
        fields=[
            "name as id", "model", "variant", "color",
            "final_price", "payment_mode", "status",
            "delivery_date", "creation as created_at",
        ],
        order_by="creation desc",
        page_length=int(page_size),
        start=(int(page) - 1) * int(page_size),
    )
    total = frappe.db.count("DMS Vehicle Sale", {"customer_id": customer_id})
    return paginated(purchases, total, int(page), int(page_size))
