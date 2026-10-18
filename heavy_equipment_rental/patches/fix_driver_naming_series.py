"""Remove naming overrides carried across the Crane Operator DocType rename."""

import frappe


def execute():
	for property_name in ("default", "options"):
		for name in frappe.get_all(
			"Property Setter",
			filters={
				"doc_type": "Crane Driver",
				"field_name": "naming_series",
				"property": property_name,
				"value": "OP-.#####",
			},
			pluck="name",
		):
			frappe.delete_doc("Property Setter", name, ignore_permissions=True)
	frappe.clear_cache(doctype="Crane Driver")
