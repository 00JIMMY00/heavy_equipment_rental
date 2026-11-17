"""Rename in place, retaining batch IDs, child rows and accounting links."""
import frappe


def execute():
    for old, new in [('Consolidated Expense', 'Grouped Expense'),
                     ('Consolidated Expense Item', 'Grouped Expense Item')]:
        if frappe.db.exists('DocType', old) and not frappe.db.exists('DocType', new):
            frappe.rename_doc('DocType', old, new, force=True, show_alert=False)
