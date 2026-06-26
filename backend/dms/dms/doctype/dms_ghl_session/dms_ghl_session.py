from frappe.model.document import Document


class DmsGhlSession(Document):
    pass


globals()["DMS" + "GHL" + "Session"] = DmsGhlSession
