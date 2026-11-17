"""Add the expense report within Financial Reports, preserving the site layout."""
import frappe


def execute():
    key = 'her_expense_report_workspace_v1'
    if frappe.db.get_default(key) or not frappe.db.exists('Workspace', 'Crane Operations'):
        return
    doc = frappe.get_doc('Workspace', 'Crane Operations')
    if not any(r.link_to == 'Crane Expense Report' for r in doc.links):
        links = list(doc.links)
        section = next((r for r in links if r.type == 'Card Break' and r.label == 'Financial Reports'), None)
        if not section:
            section = doc.append('links', dict(type='Card Break', label='Financial Reports'))
            links.append(section)
        row = doc.append('links', dict(type='Link', label='Crane Expense Report', link_type='Report',
            link_to='Crane Expense Report', is_query_report=1, report_ref_doctype='Expense Entry'))
        links.insert(links.index(section)+1, row)
        doc.set('links', links)
        card = None
        for idx, row in enumerate(doc.links, 1):
            row.idx = idx
            if row.type == 'Card Break':
                card = row
                card.link_count = 0
            elif card:
                card.link_count += 1
        previous = frappe.flags.in_patch
        frappe.flags.in_patch = True
        try:
            doc.save(ignore_permissions=True)
        finally:
            frappe.flags.in_patch = previous
    frappe.db.set_default(key, '1')
