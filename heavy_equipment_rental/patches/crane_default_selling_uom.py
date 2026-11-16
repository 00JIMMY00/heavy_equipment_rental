"""Fill master defaults without changing existing rental or invoice terms."""
import frappe


def execute():
    unit = frappe.db.get_single_value("Heavy Equipment Rental Settings", "default_selling_uom") or "Hour"
    frappe.db.sql("UPDATE `tabCrane` SET default_selling_uom=%s WHERE COALESCE(default_selling_uom, '')=''", unit)
