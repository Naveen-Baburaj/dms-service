import frappe
from frappe.model.document import Document


class DMSLead(Document):
    def before_insert(self):
        self.set_company_name()

    def before_save(self):
        self.set_company_name()

    def set_company_name(self):
        if self.company_id and not self.company_name:
            self.company_name = frappe.db.get_value(
                "DMS Company", self.company_id, "company_name"
            )

    def on_update(self):
        if self.status == "Converted" and not frappe.db.exists(
            "DMS Customer", {"email": self.email, "company_id": self.company_id}
        ):
            pass  # Conversion handled via API
