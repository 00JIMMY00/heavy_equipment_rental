import frappe


def execute():
    filters = {
        "parent": "Crane Operations",
        "parenttype": "Workspace",
        "link_to": "Grouped Expense",
        "label": "Grouped Expense",
    }
    for name in frappe.get_all("Workspace Link", filters=filters, pluck="name"):
        frappe.db.set_value("Workspace Link", name, "label", "Expenses")
    frappe.clear_document_cache("Workspace", "Crane Operations")
