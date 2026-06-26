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
    doc.contact_name = contact.contact_name
    doc.first_name = contact.first_name
    doc.last_name = contact.last_name
    doc.email = contact.email
    doc.phone = contact.phone
    doc.vehicle_interest = contact.vehicle_interest
    doc.source = contact.source
    doc.notes = contact.notes
    doc.save_target = target_label(target)
    doc.ghl_tag = ghl_tag_name()
    doc.ghl_sync_status = sync_status
    doc.ghl_sync_message = sync_message
    doc.rpa_job = rpa_job
    doc.raw_payload_json = _json(contact.to_dict())
    doc.save(ignore_permissions=True)
    return doc.name


def create_rpa_job(contact: ContactPayload, target: str, session_name: str, contacts_url: str | None, local_contact: str | None = None) -> str:
    job = frappe.new_doc("DMS RPA Job")
    job.provider = "GoHighLevel"
    job.job_type = "Add Contact"
    job.status = "Queued"
    job.save_target = target_label(target)
    job.contact = local_contact
    job.session_name = safe_session_name(session_name)
    job.contacts_url = contacts_url
    job.tag_name = ghl_tag_name()
    job.payload_json = _json(contact.to_dict())
    job.created_by_user = frappe.session.user
    job.save(ignore_permissions=True)
    return job.name


def _update_job(job_name: str, **fields) -> None:
    if not job_name:
        return
    doc = frappe.get_doc("DMS RPA Job", job_name)
    for key, value in fields.items():
        setattr(doc, key, value)
    doc.save(ignore_permissions=True)


def _update_local_contact(contact_name: str | None, **fields) -> None:
    if not contact_name:
        return
    doc = frappe.get_doc("DMS CRM Contact", contact_name)
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

    local_contact_name = None
    if final_target in {"dms", "both"}:
        local_contact_name = create_local_contact(
            contact=contact,
            target=final_target,
            sync_status="Not Requested" if final_target == "dms" else "Queued",
            sync_message="Saved locally." if final_target == "dms" else "Queued for GoHighLevel sync.",
        )

    if final_target == "dms":
        return {
            "target": final_target,
            "status": "Success",
            "message": "Contact saved to local DMS database.",
            "dms_contact": local_contact_name,
            "rpa_job": None,
            "ghl_result": None,
        }

    rpa_job_name = create_rpa_job(contact, final_target, session, final_contacts_url, local_contact_name)
    if local_contact_name:
        _update_local_contact(local_contact_name, rpa_job=rpa_job_name, ghl_sync_status="Running")
    _update_job(rpa_job_name, status="Running", started_at=_now())

    try:
        result = add_contact_to_gohighlevel(contact, final_contacts_url, session)
        status = _result_to_status(result)
        _update_job(
            rpa_job_name,
            status=status,
            result_json=_json(result.to_dict()),
            error_message="" if result.success else result.message,
            screenshot_before=result.screenshot_before,
            screenshot_after=result.screenshot_after,
            completed_at=_now(),
        )
        if local_contact_name:
            _update_local_contact(
                local_contact_name,
                ghl_sync_status=status,
                ghl_sync_message=result.message,
                ghl_contact_url=result.contact_url,
                last_synced_at=_now() if result.success else None,
            )
        return {
            "target": final_target,
            "status": status,
            "message": result.message,
            "dms_contact": local_contact_name,
            "rpa_job": rpa_job_name,
            "ghl_result": result.to_dict(),
        }
    except GHLLoginRequired as exc:
        message = str(exc)
        _update_job(rpa_job_name, status="Login Required", error_message=message, completed_at=_now())
        if local_contact_name:
            _update_local_contact(local_contact_name, ghl_sync_status="Login Required", ghl_sync_message=message)
        return {"target": final_target, "status": "Login Required", "message": message, "dms_contact": local_contact_name, "rpa_job": rpa_job_name, "ghl_result": None}
    except Exception as exc:
        message = str(exc)
        _update_job(rpa_job_name, status="Failed", error_message=message, completed_at=_now())
        if local_contact_name:
            _update_local_contact(local_contact_name, ghl_sync_status="Failed", ghl_sync_message=message)
        return {"target": final_target, "status": "Failed", "message": message, "dms_contact": local_contact_name, "rpa_job": rpa_job_name, "ghl_result": None}


def get_job_status(job_name: str) -> dict[str, Any]:
    doc = frappe.get_doc("DMS RPA Job", job_name)
    return {
        "name": doc.name,
        "provider": doc.provider,
        "job_type": doc.job_type,
        "status": doc.status,
        "save_target": doc.save_target,
        "contact": doc.contact,
        "session_name": doc.session_name,
        "contacts_url": doc.contacts_url,
        "tag_name": doc.tag_name,
        "payload_json": doc.payload_json,
        "result_json": doc.result_json,
        "error_message": doc.error_message,
        "screenshot_before": doc.screenshot_before,
        "screenshot_after": doc.screenshot_after,
        "started_at": str(doc.started_at) if doc.started_at else None,
        "completed_at": str(doc.completed_at) if doc.completed_at else None,
    }
