"""Expose existing operating agreements without rewriting historical snapshots."""
import frappe


def execute():
    frappe.reload_doc('heavy_equipment_rental','doctype','crane_operating_fee')
    frappe.reload_doc('heavy_equipment_rental','doctype','crane')
    for name in frappe.get_all('Crane',pluck='name'):
        doc=frappe.get_doc('Crane',name)
        if doc.operating_fees:
            continue
        row=doc.append('operating_fees',dict(is_company=int(doc.operator_type!='External Operator'),
            shareholder=doc.operating_shareholder if doc.operator_type=='External Operator' else None,
            basis='Grand Total',percentage=doc.operating_percentage or 0))
        row.db_insert()
