from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import frappe


INDEX_DEFINITIONS = {
    "DMS AI Conversation": [
        (
            "idx_dms_ai_conv_owner_scope",
            ["owner_key", "scope_key", "status", "last_message_at"],
        ),
    ],
    "DMS AI Message": [
        (
            "idx_dms_ai_msg_conversation_seq",
            ["conversation_id", "sequence_no"],
        ),
        (
            "idx_dms_ai_msg_owner_creation",
            ["owner_key", "creation"],
        ),
    ],
}


def _index_exists(doctype: str, index_name: str) -> bool:
    return bool(
        frappe.db.has_index(
            f"tab{doctype}",
            index_name,
        )
    )


def verify_schema() -> dict[str, bool]:
    conversation_table = bool(
        frappe.db.table_exists("DMS AI Conversation")
    )
    message_table = bool(
        frappe.db.table_exists("DMS AI Message")
    )

    return {
        "conversation_table": conversation_table,
        "message_table": message_table,
        "conversation_index": (
            conversation_table
            and _index_exists(
                "DMS AI Conversation",
                "idx_dms_ai_conv_owner_scope",
            )
        ),
        "message_sequence_index": (
            message_table
            and _index_exists(
                "DMS AI Message",
                "idx_dms_ai_msg_conversation_seq",
            )
        ),
        "message_owner_index": (
            message_table
            and _index_exists(
                "DMS AI Message",
                "idx_dms_ai_msg_owner_creation",
            )
        ),
    }


def ensure_indexes() -> dict[str, bool]:
    """Create missing chat indexes after migrate, outside migrate's transaction.

    This is intentionally an explicit post-migrate command. It does not depend
    on DocType JSON being re-imported or on on_doctype_update being called.
    """

    missing_tables = [
        doctype
        for doctype in INDEX_DEFINITIONS
        if not frappe.db.table_exists(doctype)
    ]
    if missing_tables:
        frappe.throw(
            "Missing AI memory tables: "
            + ", ".join(missing_tables)
        )

    for doctype, definitions in INDEX_DEFINITIONS.items():
        for index_name, fields in definitions:
            if not _index_exists(doctype, index_name):
                frappe.db.add_index(
                    doctype,
                    fields,
                    index_name,
                )

    state = verify_schema()
    if not all(state.values()):
        frappe.throw(
            f"AI memory index provisioning incomplete: {state}"
        )

    return state


def runtime_probe() -> dict[str, Any]:
    """Return the actual source paths imported by the initialized Frappe site."""

    module_names = [
        "dms.api.ai_agent",
        "dms.api.ai_memory",
        (
            "dms.dms.doctype.dms_ai_conversation."
            "dms_ai_conversation"
        ),
        "dms.dms.doctype.dms_ai_message.dms_ai_message",
    ]

    modules = {}
    for module_name in module_names:
        module = importlib.import_module(module_name)
        modules[module_name] = str(
            Path(inspect.getfile(module)).resolve()
        )

    ai_agent = importlib.import_module("dms.api.ai_agent")
    active_query_source = inspect.getsource(ai_agent.query)

    return {
        "app_path": str(
            Path(frappe.get_app_path("dms")).resolve()
        ),
        "modules": modules,
        "active_query_file": str(
            Path(inspect.getfile(ai_agent.query)).resolve()
        ),
        "active_query_line": inspect.getsourcelines(
            ai_agent.query
        )[1],
        "active_query_uses_memory": (
            "query_with_memory" in active_query_source
        ),
        "schema": verify_schema(),
    }
