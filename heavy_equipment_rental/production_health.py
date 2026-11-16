"""Read-only release health check, called through Bench (not a public endpoint)."""
import frappe


def check():
    required = {"frappe", "erpnext", "arab_erp_theme", "heavy_equipment_rental"}
    if not required.issubset(frappe.get_installed_apps()):
        raise RuntimeError("Required production apps are missing")
    frappe.db.sql("select 1")
    frappe.cache().ping()
    for doctype in ("Crane", "Rental Contract", "Crane Timesheet", "Expense Entry"):
        frappe.get_meta(doctype)
        frappe.db.count(doctype)
    return {"status": "ok", "apps": sorted(required)}
