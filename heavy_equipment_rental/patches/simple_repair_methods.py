"""Expose existing repair choices without changing their accounting history."""
import frappe


def execute():
    frappe.reload_doc('heavy_equipment_rental', 'doctype', 'crane_maintenance')
    for row in frappe.get_all('Crane Maintenance', fields=['name', 'repair_source', 'cost_treatment', 'repair_method']):
        if row.repair_method:
            continue
        method = {'My Stock': 'Use Stock Parts', 'External Parts': 'Supplier Bill',
                  'External Service': 'Supplier Bill', 'Supplier Bill': 'Supplier Bill'}.get(row.repair_source, 'Quick Repair')
        frappe.db.set_value('Crane Maintenance', row.name, {
            'repair_method': method,
            'use_existing_documents': int(row.repair_source in (None, '', 'Manual Documents')),
        }, update_modified=False)
