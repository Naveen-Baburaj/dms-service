"""
Sales API — Vehicle Sales, Bookings, Test Drives.
"""

import frappe
from frappe import _
from dms.utils.permissions import get_user_company, is_group_admin, require_company_access
from dms.utils.response import success, error, paginated


@frappe.whitelist()
def get_sales(page: int = 1, page_size: int = 20, status: str = None, search: str = None):
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

    docs = frappe.get_all(
        "DMS Vehicle Sale",
        filters=filters,
        fields=[
            "name as id", "customer_id", "customer_name",
            "vehicle_id", "model", "variant", "color",
            "chassis_no", "engine_no", "sale_price", "discount",
            "final_price", "payment_mode", "status",
            "company_id", "company_name", "sales_consultant",
            "delivery_date", "invoice_no",
            "creation as created_at",
        ],
        start=offset,
        page_length=page_size,
        order_by="creation desc",
    )
    total = frappe.db.count("DMS Vehicle Sale", filters=filters)
    return paginated(docs, total, page, page_size)


@frappe.whitelist()
def create_sale(
    customer_id: str,
    vehicle_id: str,
    sale_price: float,
    payment_mode: str,
    discount: float = 0,
    delivery_date: str = None,
):
    company_id = get_user_company()
    if not company_id:
        return error(_("Group Admin must specify a company_id."), 400)

    customer = frappe.get_doc("DMS Customer", customer_id)
    vehicle = frappe.get_doc("DMS Vehicle", vehicle_id)
    require_company_access(customer.company_id)

    final_price = float(sale_price) - float(discount)

    doc = frappe.new_doc("DMS Vehicle Sale")
    doc.update({
        "customer_id": customer_id,
        "customer_name": customer.customer_name,
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle.vehicle_name,
        "model": vehicle.model,
        "variant": vehicle.variant,
        "color": vehicle.color,
        "sale_price": sale_price,
        "discount": discount,
        "final_price": final_price,
        "payment_mode": payment_mode,
        "company_id": company_id,
        "company_name": frappe.db.get_value("DMS Company", company_id, "company_name") or company_id,
        "status": "Draft",
        "delivery_date": delivery_date,
        "sales_consultant": frappe.session.user,
    })
    doc.insert(ignore_permissions=False)
    frappe.db.commit()

    # Update customer total purchases
    frappe.db.set_value(
        "DMS Customer", customer_id, {
            "total_purchases": customer.total_purchases + final_price,
            "last_purchase_date": frappe.utils.today(),
        }
    )
    frappe.db.commit()
    return success(data=doc.as_dict(), http_status_code=201)


@frappe.whitelist()
def update_sale_status(sale_id: str, status: str):
    valid_statuses = ["Draft", "Confirmed", "Delivered", "Cancelled"]
    if status not in valid_statuses:
        return error(_(f"Invalid status: {status}"), 400)

    doc = frappe.get_doc("DMS Vehicle Sale", sale_id)
    require_company_access(doc.company_id)
    doc.status = status
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return success(data=doc.as_dict())


@frappe.whitelist()
def get_bookings(page: int = 1, page_size: int = 20):
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    filters = {}
    if not is_group_admin():
        company_id = get_user_company()
        if company_id and company_id != "__none__":
            filters["company_id"] = company_id

    docs = frappe.get_all(
        "DMS Booking",
        filters=filters,
        fields=[
            "name as id", "customer_id", "customer_name",
            "vehicle_id", "model", "variant", "color",
            "booking_amount", "booking_date", "expected_delivery",
            "status", "company_id", "creation as created_at",
        ],
        start=(page - 1) * page_size,
        page_length=page_size,
        order_by="creation desc",
    )
    total = frappe.db.count("DMS Booking", filters=filters)
    return paginated(docs, total, page, page_size)


@frappe.whitelist()
def get_test_drives(page: int = 1, page_size: int = 20):
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    filters = {}
    if not is_group_admin():
        company_id = get_user_company()
        if company_id and company_id != "__none__":
            filters["company_id"] = company_id

    docs = frappe.get_all(
        "DMS Test Drive",
        filters=filters,
        fields=[
            "name as id", "lead_id", "customer_id", "contact_name",
            "mobile_no", "vehicle_id", "model",
            "scheduled_date", "scheduled_time", "status",
            "feedback", "rating", "company_id", "creation as created_at",
        ],
        start=(page - 1) * page_size,
        page_length=page_size,
        order_by="scheduled_date desc",
    )
    total = frappe.db.count("DMS Test Drive", filters=filters)
    return paginated(docs, total, page, page_size)
