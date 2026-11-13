"""Keep historical yearly prices outside the active three-period price table."""

import frappe


def execute():
	for row in frappe.get_all(
		"Crane Period Price",
		filters={"parenttype": "Crane", "parentfield": "period_prices", "period": "Year"},
		fields=["name", "parent", "price"],
		limit_page_length=0,
	):
		frappe.db.set_value("Crane", row.parent, "legacy_year_price", row.price, update_modified=False)
		frappe.delete_doc("Crane Period Price", row.name, force=True, ignore_permissions=True)
