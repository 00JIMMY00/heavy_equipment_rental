"""Add the payment statement once, retaining the site's workspace arrangement."""

import frappe


def execute():
    key = 'her_payment_statement_workspace_v1'
    if frappe.db.get_default(key) or not frappe.db.exists('Workspace', 'Crane Operations'):
        return
    doc = frappe.get_doc('Workspace', 'Crane Operations')
    if not any(row.link_to == 'Mode of Payment Statement' for row in doc.links):
        links = list(doc.links)
        section = next((row for row in links if row.type == 'Card Break' and row.label == 'Financial Reports'), None)
        if not section:
            section = doc.append('links', dict(type='Card Break', label='Financial Reports'))
            links.append(section)
        link = doc.append('links', dict(type='Link', label='Mode of Payment Statement', link_type='Report',
                                       link_to='Mode of Payment Statement', is_query_report=1,
                                       report_ref_doctype='GL Entry'))
        links.insert(links.index(section) + 1, link)
        doc.set('links', links)
        card = None
        for index, row in enumerate(doc.links, 1):
            row.idx = index
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
