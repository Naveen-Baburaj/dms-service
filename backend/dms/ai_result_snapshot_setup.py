from __future__ import annotations

import frappe


SNAPSHOT_DOCTYPE = "DMS AI Result Snapshot"
INDEX_DEFINITIONS = [
    (
        "idx_dms_ai_snap_conversation_creation",
        ["conversation_id", "creation"],
    ),
    (
        "idx_dms_ai_snap_owner_scope",
        ["owner_key", "scope_key", "status", "modified"],
    ),
    (
        "idx_dms_ai_snap_source_hash",
        ["source_hash"],
    ),
]


def _index_exists(index_name: str) -> bool:
    return bool(
        frappe.db.has_index(
            f"tab{SNAPSHOT_DOCTYPE}",
            index_name,
        )
    )


def verify_schema() -> dict[str, bool]:
    table = bool(frappe.db.table_exists(SNAPSHOT_DOCTYPE))
    return {
        "snapshot_table": table,
        "conversation_creation_index": (
            table
            and _index_exists(
                "idx_dms_ai_snap_conversation_creation"
            )
        ),
        "owner_scope_index": (
            table
            and _index_exists("idx_dms_ai_snap_owner_scope")
        ),
        "source_hash_index": (
            table
            and _index_exists("idx_dms_ai_snap_source_hash")
        ),
    }


def ensure_indexes() -> dict[str, bool]:
    if not frappe.db.table_exists(SNAPSHOT_DOCTYPE):
        frappe.throw(
            f"Missing result snapshot table: {SNAPSHOT_DOCTYPE}"
        )

    for index_name, fields in INDEX_DEFINITIONS:
        if not _index_exists(index_name):
            frappe.db.add_index(
                SNAPSHOT_DOCTYPE,
                fields,
                index_name,
            )

    state = verify_schema()
    if not all(state.values()):
        frappe.throw(
            f"Result snapshot index provisioning incomplete: {state}"
        )
    return state
