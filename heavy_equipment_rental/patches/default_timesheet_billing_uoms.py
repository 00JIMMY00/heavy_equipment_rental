"""Initialize defaults without reinterpreting existing purchase prices."""

import frappe


def execute():
    for field in ("default_supplier_uom", "default_selling_uom"):
        if not frappe.db.get_single_value("Heavy Equipment Rental Settings", field):
            frappe.db.set_single_value("Heavy Equipment Rental Settings", field, "Hour")
    for sheet in frappe.get_all("Crane Timesheet", filters={"purchase_uom": ["is", "not set"]},
                                fields=["name", "purchase_invoice"]):
        unit = frappe.db.get_value("Purchase Invoice Item", {
            "parent": sheet.purchase_invoice, "parenttype": "Purchase Invoice", "idx": 1,
        }, "uom") if sheet.purchase_invoice else None
        frappe.db.set_value("Crane Timesheet", sheet.name, "purchase_uom", unit or "Hour",
                            update_modified=False)
