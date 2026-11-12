"""Archive retired invoice driver details without changing posted accounting."""

from collections import defaultdict

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


INVOICE_FIELDS = ("customer_pays_drivers_directly", "driver_direct_payment_journal_entry")
SETTINGS_FIELDS = ("driver_payment_expense_account", "driver_payment_payable_account")
ARCHIVE_FIELD = "legacy_driver_payment_data"


def _install_archive(doctype):
	create_custom_fields({doctype: [{
		"fieldname": ARCHIVE_FIELD,
		"fieldtype": "Long Text",
		"label": "Legacy Driver Payment Data",
		"hidden": 1,
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
	}]})


def execute():
	# Read raw storage before removing the child DocType and custom fields.
	# Existing archives win on repeat execution; retired SQL columns may remain.
	rows = defaultdict(list)
	if frappe.db.table_exists("Crane Invoice Driver"):
		for row in frappe.db.sql(
			"SELECT * FROM `tabCrane Invoice Driver` WHERE parenttype='Sales Invoice' ORDER BY parent, idx",
			as_dict=True,
		):
			rows[row.parent].append(dict(row))
	fields = [field for field in INVOICE_FIELDS if frappe.db.has_column("Sales Invoice", field)]
	if fields or rows:
		_install_archive("Sales Invoice")
		for invoice in frappe.db.sql(
			"SELECT name, legacy_driver_payment_data" +
			(" , " + ", ".join(fields) if fields else "") + " FROM `tabSales Invoice`",
			as_dict=True,
		):
			data = {field: invoice.get(field) for field in fields}
			data["crane_drivers"] = rows.get(invoice.name, [])
			if not invoice.get(ARCHIVE_FIELD) and any(data.values()):
				frappe.db.set_value("Sales Invoice", invoice.name, ARCHIVE_FIELD,
					frappe.as_json(data), update_modified=False)
	settings = dict(frappe.db.sql(
		"SELECT field, value FROM tabSingles WHERE doctype=%s AND field IN %s",
		("Heavy Equipment Rental Settings", SETTINGS_FIELDS),
	))
	if any(settings.values()):
		_install_archive("Heavy Equipment Rental Settings")
		if not frappe.db.get_single_value("Heavy Equipment Rental Settings", ARCHIVE_FIELD):
			frappe.db.set_single_value("Heavy Equipment Rental Settings", ARCHIVE_FIELD,
				frappe.as_json(settings), update_modified=False)
	for field in ("crane_drivers", *INVOICE_FIELDS):
		name = frappe.db.get_value("Custom Field", {"dt": "Sales Invoice", "fieldname": field})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True)
	if frappe.db.exists("DocType", "Crane Invoice Driver"):
		frappe.delete_doc("DocType", "Crane Invoice Driver", force=True, ignore_permissions=True)
	frappe.db.sql(
		"DELETE FROM tabSingles WHERE doctype=%s AND field IN %s",
		("Heavy Equipment Rental Settings", SETTINGS_FIELDS),
	)
	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Heavy Equipment Rental Settings")
