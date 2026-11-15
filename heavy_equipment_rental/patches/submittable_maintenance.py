"""Preserve existing postings while adopting native Maintenance docstatus."""
import json
import frappe


def execute():
    from heavy_equipment_rental.crane_repairs import documents
    for row in frappe.get_all('Crane Maintenance', fields=['name', 'docstatus', 'status', 'legacy_lifecycle']):
        if row.legacy_lifecycle:
            continue
        linked = documents(row.name, check_permissions=False)
        linked += [dict(doctype='Expense Entry', **r) for r in frappe.get_all(
            'Expense Entry', filters={'crane_maintenance': row.name}, fields=['name', 'docstatus'])]
        # Do not call submit/cancel hooks or touch native financial documents.
        target = row.docstatus
        if row.docstatus == 0:
            if row.status == 'Completed' or any(r['docstatus'] == 1 for r in linked):
                target = 1
            elif row.status == 'Cancelled':
                target = 2
        frappe.db.set_value('Crane Maintenance', row.name, {
            'docstatus': target,
            'legacy_lifecycle': json.dumps(dict(docstatus=row.docstatus, status=row.status, documents=linked)),
        }, update_modified=False)
        frappe.db.sql('UPDATE `tabCrane Maintenance Item` SET docstatus=%s WHERE parent=%s AND parenttype=%s',
            (target, row.name, 'Crane Maintenance'))
