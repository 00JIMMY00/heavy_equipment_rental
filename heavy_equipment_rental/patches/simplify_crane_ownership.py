"""Backfill explicit hire and ownership presentation without rewriting agreements."""
import frappe
from frappe.utils import flt


def execute():
    frappe.reload_doc('heavy_equipment_rental', 'doctype', 'crane')
    for name in frappe.get_all('Crane', pluck='name'):
        doc = frappe.get_doc('Crane', name)
        if doc.ownership_classification:
            continue
        if doc.ownership_type == 'Owned' and not doc.ownership_partners:
            row = doc.append('ownership_partners', dict(is_company=1, ownership_percentage=100, profit_percentage=100))
            row.db_insert()
        share = sum(flt(r.ownership_percentage) for r in doc.ownership_partners if r.is_company)
        classification = ('Ownership Not Recorded' if not doc.ownership_partners else
            'Company Owned' if share == 100 else 'Shared Ownership' if share else 'Externally Owned')
        frappe.db.set_value('Crane', name, dict(hired_from_supplier=int(doc.ownership_type == 'Rented'),
            ownership_classification=classification), update_modified=False)
