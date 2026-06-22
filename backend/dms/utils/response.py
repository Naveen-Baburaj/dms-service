import frappe


def success(data=None, message: str = "Success", http_status_code: int = 200):
    frappe.local.response["http_status_code"] = http_status_code
    return {"success": True, "data": data, "message": message}


def error(message: str = "An error occurred", http_status_code: int = 400, details=None):
    frappe.local.response["http_status_code"] = http_status_code
    return {
        "success": False,
        "data": None,
        "message": message,
        "details": details,
    }


def paginated(data: list, total: int, page: int, page_size: int):
    return success(
        data={
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )
