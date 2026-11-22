"""Install app-owned fields on ERPNext documents."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from heavy_equipment_rental.patches.default_rental_workspace import execute as set_default_workspace
from heavy_equipment_rental.workspace import (
    add_receivable_report, add_salary_report, add_treasury_balances_report, sync_operations_workspace,
)
from heavy_equipment_rental.item_prices import install_item_price_field


def execute():
	from heavy_equipment_rental.crane_insights import install_workspace
	install_workspace()
	from heavy_equipment_rental.consolidated_expenses_setup import seed_defaults, update_workspace
	from heavy_equipment_rental.employee_entry import setup as setup_employee_entry
	setup_employee_entry()
	for unit in ("Hour", "Day"):
		if not frappe.db.exists("UOM", unit):
			frappe.get_doc({"doctype": "UOM", "uom_name": unit, "must_be_whole_number": 0}).insert(ignore_permissions=True)
	# Retain fractional worked hours and existing invoice conversion precision.
	for doctype in ("Purchase Invoice Item", "Sales Invoice Item"):
		for field, precision in (("qty", 9 if doctype == "Sales Invoice Item" else 6), ("conversion_factor", 9)):
			if int(frappe.get_meta(doctype).get_field(field).precision or 0) < precision:
				frappe.make_property_setter({
					"doctype": doctype, "fieldname": field,
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
					int(permission in ("read", "select", "report", "export", "print")
						or (permission == "cancel" and role == "Projects Manager")),
				)
	create_custom_fields({
		"Account": [dict(fieldname="her_is_salary_account", fieldtype="Check", label="Salary Expense Account",
			insert_after="account_type", depends_on="eval:doc.root_type === 'Expense' && !doc.is_group")],
		"Sales Invoice Item": [dict(fieldname="her_rental_dates", fieldtype="Long Text",
			label="Billed Rental Dates", read_only=1, hidden=1, no_copy=1)],
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
			"label": "Rental Contract",
			"options": "Rental Contract",
			"insert_after": "crane_timesheet",
			"in_standard_filter": 1,
		}, {
			"fieldname": "crane_timesheet",
			"fieldtype": "Link",
			"label": "Crane Timesheet",
			"options": "Crane Timesheet",
			"insert_after": "crane",
			"in_standard_filter": 1,
		}, {
			"fieldname": "service_from_date",
			"hidden": 1,
			"fieldtype": "Date",
			"label": "Service From Date",
			"read_only": 1,
			"insert_after": "crane_assignment",
			"depends_on": "crane",
			"description": "Work period charged by this expense, independent of Posting Date. Rental Contract bookings supply the default period.",
		}, {
			"fieldname": "service_to_date",
			"hidden": 1,
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
			"label": "Employee",
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
	for doctype in ("Expense Entry", "Grouped Expense"):
		frappe.db.add_index(doctype, ["company", "employee", "docstatus"])
	from heavy_equipment_rental.crane_repairs import install_fields as install_repair_fields
	install_repair_fields()
	install_item_price_field()
	from heavy_equipment_rental.profit_sharing import install_fields

	install_fields()
	from heavy_equipment_rental.partner_accounts import install as install_partner_accounts
	install_partner_accounts()
	from heavy_equipment_rental.treasury_workbook import install_fields as install_workbook_fields

	install_workbook_fields()
	sync_operations_workspace()
	add_salary_report()
	add_receivable_report()
	add_treasury_balances_report()
	from heavy_equipment_rental.patches.add_expense_report_workspace import execute as add_expense_report
	add_expense_report()
	seed_defaults()
	update_workspace()
	set_default_workspace()
