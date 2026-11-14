"""Read-only dashboard using the comprehensive report's permission-checked calculations."""
import frappe
from heavy_equipment_rental.distribution_reporting import execute


@frappe.whitelist()
def get_data(filters=None):
    report = frappe.get_doc("Report", "Crane Profit Distribution")
    if not report.is_permitted():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
    return execute(frappe.parse_json(filters) or {}, dashboard=True)
