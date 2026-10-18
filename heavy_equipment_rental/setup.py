"""Install app-owned fields on ERPNext documents."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from heavy_equipment_rental.patches.default_rental_workspace import execute as set_default_workspace


def execute():
	for role in ("Projects Manager", "Projects User"):
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": "Mode of Payment", "role": role, "permlevel": 0, "if_owner": 0}
		):
			add_permission("Mode of Payment", role, ptype="select")
		update_permission_property("Mode of Payment", role, 0, "select", 1)
	create_custom_fields({
		"Sales Invoice": [{
			"fieldname": "crane_drivers",
			"fieldtype": "Table",
			"label": "Crane Drivers",
			"options": "Crane Invoice Driver",
			"insert_after": "items",
			"read_only": 1,
		}, {
			"fieldname": "customer_pays_drivers_directly",
			"fieldtype": "Check",
			"label": "Customer Pays Drivers Directly",
			"description": "Record the actual customer-to-driver payment after submitting the invoice.",
			"insert_after": "crane_drivers",
			"default": 0,
		}, {
			"fieldname": "driver_direct_payment_journal_entry",
			"fieldtype": "Link",
			"label": "Driver Direct Payment Journal Entry",
			"options": "Journal Entry",
			"insert_after": "customer_pays_drivers_directly",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		}],
	})
	set_default_workspace()
