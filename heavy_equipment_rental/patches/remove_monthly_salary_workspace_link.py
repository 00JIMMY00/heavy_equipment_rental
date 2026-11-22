import frappe


def execute():
    if not frappe.db.exists("Workspace", "Crane Operations"):
        return
    workspace = frappe.get_doc("Workspace", "Crane Operations")
    card = None
    removed = False
    for row in list(workspace.links):
        if row.type == "Card Break":
            card = row
        elif row.link_type == "Report" and row.link_to == "Monthly Salary Report":
            workspace.remove(row)
            if card:
                card.link_count = max(0, (card.link_count or 0) - 1)
            removed = True
    if removed:
        was_in_patch = frappe.flags.in_patch
        frappe.flags.in_patch = True
        try:
            workspace.save(ignore_permissions=True)
        finally:
            frappe.flags.in_patch = was_in_patch
        frappe.clear_document_cache("Workspace", workspace.name)
