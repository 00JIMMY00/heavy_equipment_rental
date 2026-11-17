"""Retain removed date metadata and dated audit history without rewriting settlements."""
import frappe
from heavy_equipment_rental.profit_sharing import dumps


def execute():
    if not frappe.db.has_column('Crane', 'agreement_effective_from'):
        return
    for row in frappe.db.sql('''select name, agreement_effective_from, agreement_history,
            legacy_agreement_data from `tabCrane`''', as_dict=True):
        if not row.legacy_agreement_data:
            frappe.db.set_value('Crane', row.name, 'legacy_agreement_data', dumps({
                'agreement_effective_from': row.agreement_effective_from,
                'agreement_history': frappe.parse_json(row.agreement_history or '[]'),
            }), update_modified=False)
