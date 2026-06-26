from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe


COMPANIES = [
    ("Honda", "Honda", "honda@dms.local", "32HONDA0001Z1"),
    ("NEXA", "NEXA", "nexa@dms.local", "32NEXA0002Z1"),
    ("Jaguar", "Jaguar", "jaguar@dms.local", "32JAGUAR003Z1"),
]

SALES = {
    "Honda": [1200000, 1450000, 1320000, 1600000, 1750000],
    "NEXA": [820000, 910000, 990000, 1040000, 1160000],
    "Jaguar": [1100000, 1180000, 1210000, 1290000, 1370000],
}

SERVICE_COUNTS = {
    "Honda": [82, 91, 86, 99, 105],
    "NEXA": [61, 68, 73, 79, 84],
    "Jaguar": [74, 80, 83, 89, 93],
}

CUSTOMERS = {
    "Honda": [("Anil Mathew", "anil.honda@example.com", "9000001001"), ("Priya Nair", "priya.honda@example.com", "9000001002"), ("Rahul Menon", "rahul.honda@example.com", "9000001003")],
    "NEXA": [("Meera Thomas", "meera.nexa@example.com", "9000002001"), ("Arjun Pillai", "arjun.nexa@example.com", "9000002002"), ("Sneha Raj", "sneha.nexa@example.com", "9000002003")],
    "Jaguar": [("Vikram Varma", "vikram.jaguar@example.com", "9000003001"), ("Diya Kurian", "diya.jaguar@example.com", "9000003002"), ("Kiran George", "kiran.jaguar@example.com", "9000003003")],
}

VEHICLES = {
    "Honda": [("Honda City ZX", "City", "ZX CVT", "White", 1600000), ("Honda Elevate VX", "Elevate", "VX MT", "Silver", 1550000), ("Honda Amaze VX", "Amaze", "VX CVT", "Red", 1050000)],
    "NEXA": [("NEXA Baleno Alpha", "Baleno", "Alpha AMT", "Blue", 1120000), ("NEXA Fronx Alpha", "Fronx", "Alpha Turbo", "Grey", 1390000), ("NEXA Grand Vitara", "Grand Vitara", "Zeta", "White", 1980000)],
    "Jaguar": [("Jaguar XE R-Dynamic", "XE", "R-Dynamic", "Black", 5200000), ("Jaguar F-Pace Prestige", "F-Pace", "Prestige", "Blue", 7800000), ("Jaguar XF Portfolio", "XF", "Portfolio", "Silver", 6900000)],
}

LEADS = {
    "Honda": ["City enquiry", "Elevate finance", "Amaze exchange", "WR-V follow-up", "Service upgrade"],
    "NEXA": ["Baleno enquiry", "Fronx test drive", "Grand Vitara quote", "Ignis lead", "XL6 corporate"],
    "Jaguar": ["F-Pace enquiry", "XE test drive", "XF finance", "I-Pace callback", "Corporate fleet"],
}

MONTHS = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]


def _dt(year: int, month: int, day: int) -> str:
    return datetime(year, month, day, 10, 0, 0).strftime("%Y-%m-%d %H:%M:%S")


def _insert_if_missing(doctype: str, filters: dict[str, Any], values: dict[str, Any]) -> str:
    existing = frappe.db.get_value(doctype, filters, "name")
    if existing:
        return existing

    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.insert(ignore_permissions=True)
    return doc.name


def _set_creation(doctype: str, name: str, creation: str) -> None:
    frappe.db.set_value(doctype, name, "creation", creation, update_modified=False)
    frappe.db.set_value(doctype, name, "modified", creation, update_modified=False)


def _seed_companies() -> dict[str, str]:
    result = {}
    for company_name, brand, email, gstin in COMPANIES:
        result[company_name] = _insert_if_missing(
            "DMS Company",
            {"company_name": company_name},
            {
                "company_name": company_name,
                "company_type": "Automotive",
                "brand": brand,
                "city": "Kochi",
                "state": "Kerala",
                "pin_code": "682001",
                "phone": "+91-484-4001001",
                "email": email,
                "gstin": gstin,
                "is_active": 1,
            },
        )
    return result


def _seed_customers(company_ids: dict[str, str]) -> dict[str, list[str]]:
    result = {}
    for company_name, rows in CUSTOMERS.items():
        result[company_name] = []
        for customer_name, email, mobile_no in rows:
            result[company_name].append(_insert_if_missing(
                "DMS Customer",
                {"email": email, "company_id": company_ids[company_name]},
                {
                    "company_id": company_ids[company_name],
                    "customer_name": customer_name,
                    "email": email,
                    "mobile_no": mobile_no,
                    "customer_type": "Individual",
                    "status": "Active",
                    "city": "Kochi",
                    "state": "Kerala",
                    "pin_code": "682001",
                    "total_purchases": 0,
                    "loyalty_points": 0,
                },
            ))
    return result


def _seed_vehicles(company_ids: dict[str, str]) -> dict[str, list[str]]:
    result = {}
    for company_name, rows in VEHICLES.items():
        result[company_name] = []
        for index, (vehicle_name, model, variant, color, price) in enumerate(rows, start=1):
            code = company_name.upper().replace(" ", "")
            result[company_name].append(_insert_if_missing(
                "DMS Vehicle",
                {"chassis_no": f"{code}-CH-{index:03d}"},
                {
                    "company_id": company_ids[company_name],
                    "vehicle_name": vehicle_name,
                    "model": model,
                    "variant": variant,
                    "color": color,
                    "year": 2026,
                    "fuel_type": "Diesel" if company_name == "Jaguar" else "Petrol",
                    "transmission": "Automatic",
                    "chassis_no": f"{code}-CH-{index:03d}",
                    "engine_no": f"{code}-EN-{index:03d}",
                    "ex_showroom_price": price,
                    "on_road_price": int(price * 1.18),
                    "stock_status": "In Stock",
                },
            ))
    return result


def _seed_sales(company_ids: dict[str, str], customer_ids: dict[str, list[str]], vehicle_ids: dict[str, list[str]]) -> int:
    count = 0
    for company_name, amounts in SALES.items():
        for index, amount in enumerate(amounts):
            year, month = MONTHS[index]
            customer_id = customer_ids[company_name][index % len(customer_ids[company_name])]
            vehicle_id = vehicle_ids[company_name][index % len(vehicle_ids[company_name])]
            invoice_no = f"INV-{company_name.upper()}-{year}{month:02d}"
            sale_name = _insert_if_missing(
                "DMS Vehicle Sale",
                {"invoice_no": invoice_no},
                {
                    "company_id": company_ids[company_name],
                    "company_name": company_name,
                    "customer_id": customer_id,
                    "vehicle_id": vehicle_id,
                    "model": frappe.db.get_value("DMS Vehicle", vehicle_id, "model"),
                    "variant": frappe.db.get_value("DMS Vehicle", vehicle_id, "variant"),
                    "color": frappe.db.get_value("DMS Vehicle", vehicle_id, "color"),
                    "chassis_no": frappe.db.get_value("DMS Vehicle", vehicle_id, "chassis_no"),
                    "engine_no": frappe.db.get_value("DMS Vehicle", vehicle_id, "engine_no"),
                    "sale_price": amount,
                    "discount": 0,
                    "final_price": amount,
                    "payment_mode": "Finance",
                    "status": "Delivered",
                    "delivery_date": f"{year}-{month:02d}-20",
                    "invoice_no": invoice_no,
                },
            )
            _set_creation("DMS Vehicle Sale", sale_name, _dt(year, month, 15))
            count += 1
    return count


def _seed_service_jobs(company_ids: dict[str, str], customer_ids: dict[str, list[str]]) -> int:
    count = 0
    for company_name, monthly_counts in SERVICE_COUNTS.items():
        for month_index, monthly_count in enumerate(monthly_counts):
            year, month = MONTHS[month_index]
            customer_id = customer_ids[company_name][month_index % len(customer_ids[company_name])]
            for sequence in range(1, monthly_count + 1):
                vehicle_reg_no = f"KL-07-{company_name[:2].upper()}-{month:02d}{sequence:03d}"
                creation = _dt(year, month, min(25, 1 + (sequence % 25)))
                job_name = _insert_if_missing(
                    "DMS Service Job",
                    {"vehicle_reg_no": vehicle_reg_no, "company_id": company_ids[company_name]},
                    {
                        "company_id": company_ids[company_name],
                        "customer_id": customer_id,
                        "customer_name": frappe.db.get_value("DMS Customer", customer_id, "customer_name"),
                        "vehicle_reg_no": vehicle_reg_no,
                        "model": "City" if company_name == "Honda" else "Baleno" if company_name == "NEXA" else "F-Pace",
                        "service_type": "General Service",
                        "km_reading": 5000 + sequence * 100,
                        "complaint": "Periodic service and inspection",
                        "labour_charges": 2500,
                        "parts_charges": 3500,
                        "total_amount": 6000,
                        "status": "Completed",
                        "expected_delivery": creation,
                        "actual_delivery": creation,
                    },
                )
                _set_creation("DMS Service Job", job_name, creation)
                count += 1
    return count


def _seed_leads(company_ids: dict[str, str]) -> int:
    count = 0
    company_index = {name: index + 1 for index, name in enumerate(SALES.keys())}
    for company_name, rows in LEADS.items():
        for index, title in enumerate(rows, start=1):
            mobile_no = f"91000{company_index[company_name]}{index:04d}"
            _insert_if_missing(
                "DMS Lead",
                {"mobile_no": mobile_no, "company_id": company_ids[company_name]},
                {
                    "company_id": company_ids[company_name],
                    "lead_name": title,
                    "email": f"lead{index}.{company_name.lower()}@example.com",
                    "mobile_no": mobile_no,
                    "status": "Open",
                    "source": "Website",
                    "vehicle_interest": title,
                    "budget": 1500000,
                    "notes": "Demo lead generated by seed script",
                    "follow_up_date": "2026-06-30",
                },
            )
            count += 1
    return count


def _seed_bookings_and_test_drives(company_ids: dict[str, str], customer_ids: dict[str, list[str]], vehicle_ids: dict[str, list[str]]) -> dict[str, int]:
    bookings = 0
    test_drives = 0
    company_index = {name: index + 1 for index, name in enumerate(SALES.keys())}
    for company_name in SALES.keys():
        for index in range(2):
            customer_id = customer_ids[company_name][index]
            vehicle_id = vehicle_ids[company_name][index]
            booking_date = f"2026-06-{10 + index:02d}"
            _insert_if_missing(
                "DMS Booking",
                {"customer_id": customer_id, "vehicle_id": vehicle_id, "booking_date": booking_date},
                {
                    "company_id": company_ids[company_name],
                    "customer_id": customer_id,
                    "vehicle_id": vehicle_id,
                    "model": frappe.db.get_value("DMS Vehicle", vehicle_id, "model"),
                    "variant": frappe.db.get_value("DMS Vehicle", vehicle_id, "variant"),
                    "color": frappe.db.get_value("DMS Vehicle", vehicle_id, "color"),
                    "booking_amount": 25000,
                    "booking_date": booking_date,
                    "expected_delivery": "2026-07-15",
                    "status": "Confirmed",
                    "notes": "Demo booking generated by seed script",
                },
            )
            bookings += 1

            mobile_no = f"92000{company_index[company_name]}{index:04d}"
            _insert_if_missing(
                "DMS Test Drive",
                {"mobile_no": mobile_no, "company_id": company_ids[company_name]},
                {
                    "company_id": company_ids[company_name],
                    "customer_id": customer_id,
                    "contact_name": frappe.db.get_value("DMS Customer", customer_id, "customer_name"),
                    "mobile_no": mobile_no,
                    "vehicle_id": vehicle_id,
                    "model": frappe.db.get_value("DMS Vehicle", vehicle_id, "model"),
                    "scheduled_date": f"2026-06-{12 + index:02d}",
                    "scheduled_time": "11:00:00",
                    "status": "Scheduled",
                },
            )
            test_drives += 1
    return {"bookings": bookings, "test_drives": test_drives}


def _service_job_reference(company_id: str, customer_id: str, offset: int) -> str | None:
    jobs = frappe.get_all(
        "DMS Service Job",
        filters={"company_id": company_id, "customer_id": customer_id},
        pluck="name",
        order_by="creation asc",
        limit_page_length=offset + 1,
    )
    if len(jobs) > offset:
        return jobs[offset]
    return jobs[0] if jobs else None


def _seed_invoices(company_ids: dict[str, str], customer_ids: dict[str, list[str]]) -> int:
    count = 0
    for company_name in SALES.keys():
        for index in range(2):
            customer_id = customer_ids[company_name][index]
            service_job = _service_job_reference(company_ids[company_name], customer_id, index)
            if not service_job:
                continue
            _insert_if_missing(
                "DMS Invoice",
                {"reference_doctype": "DMS Service Job", "reference_doc": service_job, "company_id": company_ids[company_name]},
                {
                    "company_id": company_ids[company_name],
                    "invoice_type": "Service",
                    "customer_id": customer_id,
                    "reference_doctype": "DMS Service Job",
                    "reference_doc": service_job,
                    "invoice_date": f"2026-06-{18 + index:02d}",
                    "subtotal": 6000,
                    "discount": 0,
                    "tax_amount": 1080,
                    "total_amount": 7080,
                    "payment_status": "Paid",
                    "paid_amount": 7080,
                    "balance_amount": 0,
                    "due_date": f"2026-06-{25 + index:02d}",
                },
            )
            count += 1
    return count


@frappe.whitelist()
def seed() -> dict[str, Any]:
    company_ids = _seed_companies()
    customer_ids = _seed_customers(company_ids)
    vehicle_ids = _seed_vehicles(company_ids)
    sales = _seed_sales(company_ids, customer_ids, vehicle_ids)
    service_jobs = _seed_service_jobs(company_ids, customer_ids)
    leads = _seed_leads(company_ids)
    activity = _seed_bookings_and_test_drives(company_ids, customer_ids, vehicle_ids)
    invoices = _seed_invoices(company_ids, customer_ids)
    frappe.db.commit()
    return {
        "status": "success",
        "message": "DMS demo data is ready.",
        "companies": len(company_ids),
        "customers": sum(len(items) for items in customer_ids.values()),
        "vehicles": sum(len(items) for items in vehicle_ids.values()),
        "sales": sales,
        "service_jobs": service_jobs,
        "leads": leads,
        "bookings": activity["bookings"],
        "test_drives": activity["test_drives"],
        "invoices": invoices,
    }
