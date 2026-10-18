"""Create linked Employee records for drivers created before the rename.

Legacy drivers did not collect HR details. Leave unknown details empty so they can
be completed by HR without inventing personal information.
"""

import frappe


def execute():
	for driver in frappe.get_all(
		"Crane Driver", filters={"employee": ["is", "not set"]}, fields=["name", "operator_name", "phone"]
	):
		first, _, remainder = driver.operator_name.strip().partition(" ")
		employee = frappe.get_doc({
			"doctype": "Employee",
			"first_name": first,
			"last_name": remainder,
			"cell_number": driver.phone,
			"status": "Active",
		})
		employee.flags.ignore_mandatory = True
		employee.insert(ignore_permissions=True)
		frappe.db.set_value("Crane Driver", driver.name, "employee", employee.name, update_modified=False)
