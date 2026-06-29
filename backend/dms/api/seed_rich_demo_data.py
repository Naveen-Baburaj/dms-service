import random
from datetime import datetime
from typing import Any

import frappe
from frappe.utils import add_days, add_months, now_datetime


MONTHS_BACK = 36
RANDOM_SEED = 4262026
random.seed(RANDOM_SEED)


COMPANIES = {
    "Honda": {
        "models": ["City", "Amaze", "Elevate", "WR-V", "Jazz", "Civic", "Accord"],
        "customers": [
            ("John Kurien", "9000011101", "john.kurien@example.com"),
            ("Aisha Rahman", "9000011102", "aisha.rahman@example.com"),
            ("Rohit Varghese", "9000011103", "rohit.varghese@example.com"),
            ("Neha Iyer", "9000011104", "neha.iyer@example.com"),
            ("Manu Joseph", "9000011105", "manu.joseph@example.com"),
            ("Farah Khan", "9000011106", "farah.khan@example.com"),
            ("Anil Mathew", "9000001001", "anil.honda@example.com"),
            ("Priya Nair", "9000001002", "priya.honda@example.com"),
            ("Rahul Menon", "9000001003", "rahul.honda@example.com"),
            ("Sreya Das", "9000011107", "sreya.das@example.com"),
            ("Nikhil Thomas", "9000011108", "nikhil.thomas@example.com"),
            ("Leena George", "9000011109", "leena.george@example.com"),
            ("Ashwin Kumar", "9000011110", "ashwin.kumar@example.com"),
            ("Megha Suresh", "9000011111", "megha.suresh@example.com"),
            ("Vivek Paul", "9000011112", "vivek.paul@example.com"),
        ],
    },
    "NEXA": {
        "models": ["Baleno", "Fronx", "Grand Vitara", "XL6", "Ignis", "Ciaz"],
        "customers": [
            ("Ibrahim Sait", "9000021101", "ibrahim.sait@example.com"),
            ("Nisha Paul", "9000021102", "nisha.paul@example.com"),
            ("Dev Menon", "9000021103", "dev.menon@example.com"),
            ("Sana Thomas", "9000021104", "sana.thomas@example.com"),
            ("Karthik Rao", "9000021105", "karthik.rao@example.com"),
            ("Maria Dsouza", "9000021106", "maria.dsouza@example.com"),
            ("Meera Thomas", "9000002001", "meera.nexa@example.com"),
            ("Arjun Pillai", "9000002002", "arjun.nexa@example.com"),
            ("Sneha Raj", "9000002003", "sneha.nexa@example.com"),
            ("Adil Hussain", "9000021107", "adil.hussain@example.com"),
            ("Naveena Krishnan", "9000021108", "naveena.krishnan@example.com"),
            ("Gokul Prasad", "9000021109", "gokul.prasad@example.com"),
            ("Rima Francis", "9000021110", "rima.francis@example.com"),
            ("Varun Balan", "9000021111", "varun.balan@example.com"),
            ("Lakshmi Pillai", "9000021112", "lakshmi.pillai@example.com"),
        ],
    },
    "Jaguar": {
        "models": ["XE", "XF", "F-Pace", "I-Pace", "E-Pace", "F-Type"],
        "customers": [
            ("Aditya Kapoor", "9000031101", "aditya.kapoor@example.com"),
            ("Sara Mathew", "9000031102", "sara.mathew@example.com"),
            ("Neil Fernandes", "9000031103", "neil.fernandes@example.com"),
            ("Rhea Varma", "9000031104", "rhea.varma@example.com"),
            ("Kabir Nair", "9000031105", "kabir.nair@example.com"),
            ("Tanya George", "9000031106", "tanya.george@example.com"),
            ("Vikram Varma", "9000003001", "vikram.jaguar@example.com"),
            ("Diya Kurian", "9000003002", "diya.jaguar@example.com"),
            ("Kiran George", "9000003003", "kiran.jaguar@example.com"),
            ("Maya Kapoor", "9000031107", "maya.kapoor@example.com"),
            ("Armaan Shah", "9000031108", "armaan.shah@example.com"),
            ("Elena Dcruz", "9000031109", "elena.dcruz@example.com"),
            ("Sahil Verma", "9000031110", "sahil.verma@example.com"),
            ("Noel Abraham", "9000031111", "noel.abraham@example.com"),
            ("Ira Menon", "9000031112", "ira.menon@example.com"),
        ],
    },
}


def has_field(doctype: str, fieldname: str) -> bool:
    if fieldname in {"name", "creation", "modified", "owner"}:
        return True
    try:
        return bool(frappe.get_meta(doctype).has_field(fieldname))
    except Exception:
        return False


def select_options(doctype: str, fieldname: str) -> list[str]:
    try:
        df = frappe.get_meta(doctype).get_field(fieldname)
        if not df or df.fieldtype != "Select" or not df.options:
            return []
        return [opt.strip() for opt in str(df.options).splitlines() if opt.strip()]
    except Exception:
        return []


def sanitize_select_values(doctype: str, values: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(values)

    replacement_map = {
        "WhatsApp": "Digital",
        "Booked": "Pending",
        "Confirmed": "Pending",
        "Ready for Delivery": "Completed",
        "Partially Paid": "Pending",
        "Unavailable": "Out of Stock",
        "Qualified": "Open",
    }

    preferred_safe_values = [
        "Open",
        "Pending",
        "Active",
        "In Stock",
        "Paid",
        "Completed",
        "Digital",
        "Website",
        "Walk-in",
    ]

    for fieldname, value in list(cleaned.items()):
        if value in (None, ""):
            continue

        options = select_options(doctype, fieldname)
        if not options:
            continue

        value_text = str(value)
        if value_text in options:
            continue

        replacement = replacement_map.get(value_text)
        if replacement and replacement in options:
            cleaned[fieldname] = replacement
            continue

        for candidate in preferred_safe_values:
            if candidate in options:
                cleaned[fieldname] = candidate
                break
        else:
            cleaned[fieldname] = options[0]

    return cleaned


def valid_filters(doctype: str, filters: dict[str, Any] | None) -> dict[str, Any]:
    if not filters:
        return {}
    return {k: v for k, v in filters.items() if has_field(doctype, k)}


def exists(doctype: str, filters: dict[str, Any] | None) -> bool:
    safe_filters = valid_filters(doctype, filters)
    if not safe_filters:
        return False
    try:
        return bool(frappe.db.exists(doctype, safe_filters))
    except Exception:
        return False


def clean_values(doctype: str, values: dict[str, Any]) -> dict[str, Any]:
    values = sanitize_select_values(doctype, values)
    return {key: value for key, value in values.items() if has_field(doctype, key)}


def insert_doc(
    doctype: str,
    values: dict[str, Any],
    duplicate_filters: dict[str, Any] | None = None,
    creation: str | None = None,
) -> str | None:
    if exists(doctype, duplicate_filters):
        return None

    clean = clean_values(doctype, values)
    doc = frappe.get_doc({"doctype": doctype, **clean})
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_links = True
    doc.flags.ignore_validate = True

    try:
        doc.insert(ignore_permissions=True)
    except Exception as exc:
        print(f"SKIPPED {doctype}: {exc}")
        frappe.db.rollback()
        return None

    if creation:
        try:
            frappe.db.sql(
                f"update `tab{doctype}` set creation=%s, modified=%s where name=%s",
                (creation, creation, doc.name),
            )
        except Exception:
            pass

    return doc.name


def make_creation(months_ago: int = 0, days_offset: int = 0, hour: int = 11) -> str:
    dt = add_months(now_datetime(), -months_ago)
    dt = add_days(dt, days_offset)
    return dt.replace(hour=hour, minute=30, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def random_price(company: str) -> int:
    if company == "Jaguar":
        return random.randint(4_500_000, 9_500_000)
    if company == "NEXA":
        return random.randint(750_000, 2_400_000)
    return random.randint(850_000, 2_800_000)


def seed_customers(months_back: int) -> int:
    created = 0

    for company, info in COMPANIES.items():
        for idx, (name, mobile, email) in enumerate(info["customers"]):
            creation = make_creation(months_ago=(idx * 2) % months_back, days_offset=idx % 20)

            values = {
                "company_id": company,
                "company_name": company,
                "customer_name": name,
                "customer_type": "Individual",
                "mobile_no": mobile,
                "email": email,
                "status": "Active",
            }

            result = insert_doc(
                "DMS Customer",
                values,
                duplicate_filters={"email": email},
                creation=creation,
            )
            if result:
                created += 1

    return created


def seed_leads(months_back: int) -> int:
    created = 0
    sources = ["Website", "Cold Calling", "Referral", "Social Media", "Walk-in", "Exhibition", "Campaign", "Digital"]
    statuses = ["Open", "Open", "Pending", "Active"]

    for company, info in COMPANIES.items():
        models = info["models"]

        for month_ago in range(months_back):
            for lead_no in range(3):
                model = models[(month_ago + lead_no) % len(models)]
                lead_name = random.choice([
                    f"{model} enquiry",
                    f"{model} finance query",
                    f"{model} exchange request",
                    f"{model} test drive request",
                    f"{model} callback request",
                    f"Corporate enquiry for {model}",
                ])

                email = f"rich.lead.{company.lower()}.{month_ago:02d}.{lead_no}@example.com"
                mobile = f"91{1 + list(COMPANIES.keys()).index(company)}{month_ago:02d}{lead_no}55{100 + month_ago:03d}"

                values = {
                    "company_id": company,
                    "company_name": company,
                    "lead_name": lead_name,
                    "mobile_no": mobile,
                    "email": email,
                    "status": random.choice(statuses),
                    "source": random.choice(sources),
                    "vehicle_interest": model,
                }

                result = insert_doc(
                    "DMS Lead",
                    values,
                    duplicate_filters={"email": email},
                    creation=make_creation(months_ago=month_ago, days_offset=lead_no + 1),
                )
                if result:
                    created += 1

    return created


def seed_vehicles() -> int:
    created = 0
    colors = ["White", "Black", "Silver", "Red", "Blue", "Grey", "Brown"]
    statuses = ["In Stock", "In Stock", "In Stock", "Pending", "Sold"]

    for company, info in COMPANIES.items():
        for idx, model in enumerate(info["models"]):
            for unit in range(5):
                variant = random.choice(["Base", "VX", "ZX", "Alpha", "Top", "Luxury"])
                color = colors[(idx + unit) % len(colors)]
                stock_status = statuses[(idx + unit) % len(statuses)]
                vehicle_name = f"RICH {company} {model} {variant} {color} Unit {unit + 1}"

                values = {
                    "company_id": company,
                    "company_name": company,
                    "vehicle_name": vehicle_name,
                    "model": model,
                    "variant": variant,
                    "color": color,
                    "stock_status": stock_status,
                    "status": stock_status,
                }

                result = insert_doc(
                    "DMS Vehicle",
                    values,
                    duplicate_filters={"company_id": company, "vehicle_name": vehicle_name},
                    creation=make_creation(months_ago=random.randint(0, 18), days_offset=random.randint(1, 20)),
                )
                if result:
                    created += 1

    return created


def seed_sales_and_invoices(months_back: int) -> dict[str, int]:
    created = {"sales": 0, "invoices": 0}

    for company, info in COMPANIES.items():
        customers = info["customers"]
        models = info["models"]

        for month_ago in range(months_back):
            sales_this_month = 2 + (month_ago % 3)

            for sale_no in range(sales_this_month):
                customer_name, mobile, email = customers[(month_ago + sale_no) % len(customers)]
                model = models[(month_ago + sale_no) % len(models)]
                variant = random.choice(["Base", "VX", "ZX", "Alpha", "Top", "Luxury"])
                price = random_price(company)
                invoice_no = f"RICH-INV-{company}-{month_ago:02d}-{sale_no:02d}"
                creation = make_creation(months_ago=month_ago, days_offset=sale_no + 2, hour=12)

                sale_values = {
                    "company_id": company,
                    "company_name": company,
                    "customer_name": customer_name,
                    "model": model,
                    "variant": variant,
                    "final_price": price,
                    "payment_mode": random.choice(["Cash", "Finance", "UPI", "Bank Transfer"]),
                    "status": "Completed",
                    "invoice_no": invoice_no,
                }

                sale = insert_doc(
                    "DMS Vehicle Sale",
                    sale_values,
                    duplicate_filters={"invoice_no": invoice_no},
                    creation=creation,
                )
                if sale:
                    created["sales"] += 1

                invoice_values = {
                    "company_id": company,
                    "company_name": company,
                    "customer_name": customer_name,
                    "invoice_no": invoice_no,
                    "invoice_type": "Vehicle Sale",
                    "total_amount": price,
                    "payment_status": random.choice(["Paid", "Paid", "Pending"]),
                    "status": random.choice(["Paid", "Pending", "Completed"]),
                    "reference_doc": sale or invoice_no,
                    "due_date": add_days(datetime.strptime(creation, "%Y-%m-%d %H:%M:%S"), 15).strftime("%Y-%m-%d"),
                }

                invoice = insert_doc(
                    "DMS Invoice",
                    invoice_values,
                    duplicate_filters={"invoice_no": invoice_no},
                    creation=creation,
                )
                if invoice:
                    created["invoices"] += 1

    return created


def seed_bookings_and_test_drives(months_back: int) -> dict[str, int]:
    created = {"bookings": 0, "test_drives": 0}

    for company, info in COMPANIES.items():
        customers = info["customers"]
        models = info["models"]

        for month_ago in range(months_back):
            for idx in range(2):
                customer_name, mobile, email = customers[(month_ago + idx) % len(customers)]
                model = models[(month_ago + idx) % len(models)]
                creation = make_creation(months_ago=month_ago, days_offset=idx + 5, hour=13)

                booking_values = {
                    "company_id": company,
                    "company_name": company,
                    "customer_name": customer_name,
                    "model": model,
                    "variant": random.choice(["Base", "VX", "ZX", "Alpha", "Top"]),
                    "booking_amount": random.randint(25_000, 150_000),
                    "booking_date": creation[:10],
                    "expected_delivery": add_days(datetime.strptime(creation, "%Y-%m-%d %H:%M:%S"), 30).strftime("%Y-%m-%d"),
                    "status": random.choice(["Pending", "Active", "Open"]),
                }

                booking = insert_doc(
                    "DMS Booking",
                    booking_values,
                    duplicate_filters={
                        "company_id": company,
                        "customer_name": customer_name,
                        "model": model,
                        "booking_date": creation[:10],
                    },
                    creation=creation,
                )
                if booking:
                    created["bookings"] += 1

                test_drive_values = {
                    "company_id": company,
                    "company_name": company,
                    "contact_name": customer_name,
                    "customer_name": customer_name,
                    "mobile_no": mobile,
                    "email": email,
                    "model": model,
                    "scheduled_date": add_days(datetime.strptime(creation, "%Y-%m-%d %H:%M:%S"), 3).strftime("%Y-%m-%d"),
                    "scheduled_time": f"{10 + idx}:00:00",
                    "status": random.choice(["Pending", "Completed", "Open"]),
                }

                test_drive = insert_doc(
                    "DMS Test Drive",
                    test_drive_values,
                    duplicate_filters={
                        "company_id": company,
                        "contact_name": customer_name,
                        "model": model,
                        "scheduled_date": test_drive_values["scheduled_date"],
                    },
                    creation=creation,
                )
                if test_drive:
                    created["test_drives"] += 1

    return created


def seed_service_jobs(months_back: int) -> int:
    created = 0
    service_types = ["Periodic Service", "Brake Inspection", "Oil Change", "AC Repair", "Body Work", "Engine Check"]
    statuses = ["Open", "Pending", "Completed", "Active"]

    for company, info in COMPANIES.items():
        customers = info["customers"]
        models = info["models"]

        for month_ago in range(months_back):
            for idx in range(3):
                customer_name, mobile, email = customers[(month_ago + idx) % len(customers)]
                model = models[(month_ago + idx) % len(models)]
                reg_no = f"KL-{10 + list(COMPANIES.keys()).index(company)}-RICH-{month_ago:02d}{idx:02d}"

                values = {
                    "company_id": company,
                    "company_name": company,
                    "customer_name": customer_name,
                    "vehicle_reg_no": reg_no,
                    "model": model,
                    "service_type": service_types[(month_ago + idx) % len(service_types)],
                    "total_amount": random.randint(2_500, 45_000),
                    "status": random.choice(statuses),
                }

                result = insert_doc(
                    "DMS Service Job",
                    values,
                    duplicate_filters={"company_id": company, "vehicle_reg_no": reg_no},
                    creation=make_creation(months_ago=month_ago, days_offset=idx + 8, hour=14),
                )
                if result:
                    created += 1

    return created


def run(months_back: int = MONTHS_BACK):
    months_back = int(months_back or MONTHS_BACK)

    summary = {
        "months_back": months_back,
        "customers_created": seed_customers(months_back),
        "leads_created": seed_leads(months_back),
        "vehicles_created": seed_vehicles(),
    }

    summary.update(seed_sales_and_invoices(months_back))
    summary.update(seed_bookings_and_test_drives(months_back))
    summary["service_jobs_created"] = seed_service_jobs(months_back)

    frappe.db.commit()

    print("\nRich DMS demo data seed completed.")
    for key, value in summary.items():
        print(f"{key}: {value}")

    return summary
