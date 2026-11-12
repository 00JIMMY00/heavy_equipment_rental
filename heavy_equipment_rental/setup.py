"""Install app-owned fields on ERPNext documents."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from heavy_equipment_rental.patches.default_rental_workspace import execute as set_default_workspace
from heavy_equipment_rental.workspace import sync_operations_workspace
from heavy_equipment_rental.item_prices import install_item_price_field


def execute():
	for unit in ("Hour", "Day", "Month"):
		if not frappe.db.exists("UOM", unit):
			frappe.get_doc({"doctype": "UOM", "uom_name": unit, "must_be_whole_number": 0}).insert(ignore_permissions=True)
	# Retain fractional worked hours and existing invoice conversion precision.
	for field, precision in (("qty", 6), ("conversion_factor", 9)):
		if int(frappe.get_meta("Purchase Invoice Item").get_field(field).precision or 0) < precision:
			frappe.make_property_setter({
				"doctype": "Purchase Invoice Item", "fieldname": field,
				"property": "precision", "value": str(precision), "property_type": "Select",
			}, module="Heavy Equipment Rental")
	if not frappe.get_meta("Expense Entry Type").show_title_field_in_link:
		frappe.make_property_setter({
			"doctype": "Expense Entry Type",
			"doctype_or_field": "DocType",
			"property": "show_title_field_in_link",
			"value": "1",
			"property_type": "Check",
		}, module="Heavy Equipment Rental")
	# HER enables inline editing on the shared expense rows without modifying its owner app.
	frappe.make_property_setter({
		"doctype": "Expense Entry Detail", "doctype_or_field": "DocType",
		"property": "editable_grid", "value": "1", "property_type": "Check",
	}, module="Heavy Equipment Rental")
	for field, columns in (("expense_entry_type", 5), ("expense_entry_account", 3), ("amount", 2)):
		frappe.make_property_setter({
			"doctype": "Expense Entry Detail", "fieldname": field,
			"property": "columns", "value": str(columns), "property_type": "Int",
		}, module="Heavy Equipment Rental")

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
			"fieldname": "service_from_date",
			"fieldtype": "Date",
			"label": "Service From Date",
			"read_only": 1,
			"insert_after": "crane_assignment",
			"depends_on": "crane",
			"description": "Work period charged by this expense, independent of Posting Date. Assignment bookings supply the default period.",
		}, {
			"fieldname": "service_to_date",
			"fieldtype": "Date",
			"label": "Service To Date",
			"read_only": 1,
			"insert_after": "service_from_date",
			"depends_on": "crane",
		}, {
			"fieldname": "crane_maintenance",
			"fieldtype": "Link",
			"label": "Crane Maintenance",
			"options": "Crane Maintenance",
			"insert_after": "service_to_date",
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
	})
	install_item_price_field()
	from heavy_equipment_rental.profit_sharing import install_fields

	install_fields()
	from heavy_equipment_rental.partner_accounts import install as install_partner_accounts
	install_partner_accounts()
	from heavy_equipment_rental.treasury_workbook import install_fields as install_workbook_fields

	install_workbook_fields()
	set_default_workspace()
	sync_operations_workspace()
