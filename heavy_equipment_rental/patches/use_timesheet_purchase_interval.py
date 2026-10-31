"""Archive removed manual purchase terms without changing posted invoices."""

import frappe


def execute():
    if not all(frappe.db.has_column("Crane Timesheet", field) for field in ("purchase_qty", "purchase_rate_unit")):
        return
    for row in frappe.db.sql("""SELECT name, purchase_qty, purchase_rate_unit, purchase_rate
        FROM `tabCrane Timesheet` WHERE (purchase_qty != 0 OR COALESCE(purchase_rate_unit, '') != '')
        AND COALESCE(legacy_purchase_terms, '') = ''""", as_dict=True):
        frappe.db.set_value("Crane Timesheet", row.name, "legacy_purchase_terms", frappe.as_json({
            "purchase_qty": row.purchase_qty, "purchase_rate_unit": row.purchase_rate_unit,
            "purchase_rate": row.purchase_rate,
        }), update_modified=False)
