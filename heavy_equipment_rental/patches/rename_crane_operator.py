"""Keep existing driver records and timesheet links when renaming the DocType."""

import frappe


def execute():
	if frappe.db.exists("DocType", "Crane Operator") and not frappe.db.exists("DocType", "Crane Driver"):
		frappe.rename_doc("DocType", "Crane Operator", "Crane Driver", force=True, show_alert=False)
