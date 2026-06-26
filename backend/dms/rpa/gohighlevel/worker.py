from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import frappe

from .config import ghl_contacts_url, ghl_tag_name, safe_session_name
from .schemas import ContactPayload, GHLLoginRequired, RPAResult, normalize_target, target_label
from .skills import add_contact_to_gohighlevel


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, indent=2)


def create_local_contact(contact: ContactPayload, target: str, sync_status: str = "Not Requested", sync_message: str = "", rpa_job: str | None = None) -> str:
    doc = frappe.new_doc("DMS CRM Contact")
    for key, value in {
        "contact_name": contact.contact_name,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "phone": contact.phone,
        "vehicle_interest": contact.vehicle_interest,
        "source": contact.source,
        "notes": contact.notes,
        "save_target": target_label(target),
        "ghl_tag": ghl_tag_name(),
        "ghl_sync_status": sync_status,
        "ghl_sync_message": sync_message,
        "rpa_job": rpa_job,
        "raw_payload_json": _json(contact.to_dict()),
    }.items():
        setattr(doc, key, value)
    doc.save(ignore_permissions=True)
    return doc.name


def create_rpa_job(contact: ContactPayload, target: str, session_name: str, contacts_url: str | None, local_contact: str | None = None) -> str:
    job = frappe.new_doc("DMS RPA Job")
    for key, value in {
        "provider": "GoHighLevel",
        "job_type": "Add Contact",
        "status": "Queued",
        "save_target": target_label(target),
        "contact": local_contact,
        "session_name": safe_session_name(session_name),
        "contacts_url": contacts_url,
        "tag_name": ghl_tag_name(),
        "payload_json": _json(contact.to_dict()),
        "created_by_user": frappe.session.user,
    }.items():
        setattr(job, key, value)
    job.save(ignore_permissions=True)
    return job.name


def _update_doc(doctype: str, name: str | None, **fields) -> None:
    if not name:
        return
    doc = frappe.get_doc(doctype, name)
    for key, value in fields.items():
        setattr(doc, key, value)
    doc.save(ignore_permissions=True)


def _result_to_status(result: RPAResult) -> str:
    if result.status == "Login Required":
        return "Login Required"
    return "Success" if result.success else "Failed"


def save_contact(contact_data: dict[str, Any], target: str, contacts_url: str | None = None, session_name: str | None = None) -> dict[str, Any]:
    final_target = normalize_target(target)
    session = safe_session_name(session_name)
    contact = ContactPayload.from_dict(contact_data)
    final_contacts_url = contacts_url or ghl_contacts_url()

    local_contact = None
    if final_target in {"dms", "both"}:
        local_contact = create_local_contact(
            contact,
            final_target,
            "Not Requested" if final_target == "dms" else "Queued",
            "Saved locally." if final_target == "dms" else "Queued for GHL sync.",
        )

    if final_target == "dms":
        return {"target": final_target, "status": "Success", "message": "Contact saved locally.", "dms_contact": local_contact, "rpa_job": None, "ghl_result": None}

    job = create_rpa_job(contact, final_target, session, final_contacts_url, local_contact)
    if local_contact:
        _update_doc("DMS CRM Contact", local_contact, rpa_job=job, ghl_sync_status="Running")
    _update_doc("DMS RPA Job", job, status="Running", started_at=_now())

    try:
        result = add_contact_to_gohighlevel(contact, final_contacts_url, session)
        status = _result_to_status(result)
        _update_doc("DMS RPA Job", job, status=status, result_json=_json(result.to_dict()), error_message="" if result.success else result.message, completed_at=_now())
        if local_contact:
            _update_doc("DMS CRM Contact", local_contact, ghl_sync_status=status, ghl_sync_message=result.message, ghl_contact_url=result.contact_url, last_synced_at=_now() if result.success else None)
        return {"target": final_target, "status": status, "message": result.message, "dms_contact": local_contact, "rpa_job": job, "ghl_result": result.to_dict()}
    except GHLLoginRequired as exc:
        message = str(exc)
        _update_doc("DMS RPA Job", job, status="Login Required", error_message=message, completed_at=_now())
        if local_contact:
            _update_doc("DMS CRM Contact", local_contact, ghl_sync_status="Login Required", ghl_sync_message=message)
        return {"target": final_target, "status": "Login Required", "message": message, "dms_contact": local_contact, "rpa_job": job, "ghl_result": None}
    except Exception as exc:
        message = str(exc)
        _update_doc("DMS RPA Job", job, status="Failed", error_message=message, completed_at=_now())
        if local_contact:
            _update_doc("DMS CRM Contact", local_contact, ghl_sync_status="Failed", ghl_sync_message=message)
        return {"target": final_target, "status": "Failed", "message": message, "dms_contact": local_contact, "rpa_job": job, "ghl_result": None}


def get_job_status(job_name: str) -> dict[str, Any]:
    doc = frappe.get_doc("DMS RPA Job", job_name)
    return {key: getattr(doc, key, None) for key in ["name", "provider", "job_type", "status", "save_target", "contact", "session_name", "contacts_url", "tag_name", "payload_json", "result_json", "error_message", "started_at", "completed_at"]}
