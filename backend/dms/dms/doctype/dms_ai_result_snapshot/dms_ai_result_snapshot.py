from __future__ import annotations

import json

import frappe
from frappe.model.document import Document


class DMSAIResultSnapshot(Document):
    def validate(self):
        if self.status not in {
            "Active",
            "Archived",
            "Expired",
        }:
            frappe.throw(
                "Invalid result snapshot status."
            )

        try:
            dataset = json.loads(
                self.dataset_json or "{}"
            )
        except Exception as exc:
            frappe.throw(
                f"Invalid analytical dataset JSON: {exc}"
            )

        if not isinstance(dataset, dict):
            frappe.throw(
                "Analytical dataset must be a JSON object."
            )

        source_hash = str(self.source_hash or "")
        if len(source_hash) != 64:
            frappe.throw(
                "Result snapshot source hash must be SHA-256."
            )
