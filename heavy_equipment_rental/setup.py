"""Install app-owned fields on ERPNext documents."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from heavy_equipment_rental.patches.default_rental_workspace import execute as set_default_workspace
from heavy_equipment_rental.workspace import sync_operations_workspace
from heavy_equipment_rental.item_prices import install_item_price_field


def execute():
	for role in ("Projects Manager", "Projects User"):
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": "Mode of Payment", "role": role, "permlevel": 0, "if_owner": 0}
		):
			add_permission("Mode of Payment", role, ptype="select")
		update_permission_property("Mode of Payment", role, 0, "select", 1)
		for doctype in ("Expense Entry", "Expense Entry Type"):
			if not frappe.db.exists(
				"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
			):
				add_permission(doctype, role, ptype="read")
			for permission in (("read", "select") if doctype == "Expense Entry Type" else
				("read", "write", "create", "delete", "report", "export", "print", "submit", "amend", "cancel")):
				update_permission_property(
					doctype, role, 0, permission,
					0 if permission == "cancel" and role == "Projects User" else 1,
				)
	create_custom_fields({
		"Expense Entry Type": [{
			"fieldname": "rental_legacy_description",
			"fieldtype": "Small Text",
			"label": "Legacy Description",
			"insert_after": "account",
			"read_only": 1,
		}],
		"Expense Entry": [{
			"fieldname": "crane",
			"fieldtype": "Link",
			"label": "Crane",
			"options": "Crane",
			"insert_after": "company",
			"in_list_view": 1,
			"in_standard_filter": 1,
		}, {
			"fieldname": "crane_assignment",
			"fieldtype": "Link",
			"label": "Crane Assignment",
			"options": "Crane Assignment",
			"insert_after": "crane",
			"in_standard_filter": 1,
		}, {
			"fieldname": "crane_maintenance",
			"fieldtype": "Link",
			"label": "Crane Maintenance",
			"options": "Crane Maintenance",
			"insert_after": "crane_assignment",
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		}, {
			"fieldname": "employee",
			"fieldtype": "Link",
			"label": "Crane Driver (Employee)",
			"options": "Employee",
			"insert_after": "crane_maintenance",
			"in_standard_filter": 1,
		}, {
			"fieldname": "receipt",
			"fieldtype": "Attach",
			"label": "Receipt",
			"insert_after": "description",
		}],
		"Sales Invoice": [{
			"fieldname": "crane_drivers",
			"fieldtype": "Table",
			"label": "Crane Operators",
			"options": "Crane Invoice Driver",
			"insert_after": "items",
			"read_only": 1,
		}, {
			"fieldname": "customer_pays_drivers_directly",
			"fieldtype": "Check",
			"label": "Customer Pays Drivers Directly",
			"description": "Record the actual customer-to-operator payment after submitting the invoice.",
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
	install_item_price_field()
	set_default_workspace()
	sync_operations_workspace()
