"""Preserve existing contracts and cash repairs while enabling the native workflow."""

import frappe


def execute():
	from heavy_equipment_rental.crane_repairs import install_fields
	from heavy_equipment_rental.rental_items import default_service_item

	install_fields()
	default_service_item()
	if frappe.db.get_single_value("Heavy Equipment Rental Settings", "native_workflow_migrated"):
		return
	# These are previous behavior labels, not inferred ownership amounts or new
	# agreement versions. Never modify snapshots, invoices, stock or GL entries.
	for row in frappe.get_all("Crane", fields=["name", "asset", "ownership_type"]):
		values = dict(settlement_approval="On Invoice Submission",
			distribution_posting="Source Revenue Accounts", include_depreciation=0)
		if row.asset:
			values["asset_accounting_basis"] = ("Third-party Custody" if row.ownership_type in
				("Rented", "Operated for Owner") else "Whole Crane")
		frappe.db.set_value("Crane", row.name, values, update_modified=False)
	frappe.db.sql("UPDATE `tabCrane Maintenance` SET cost_treatment='Cash Expense'")
	frappe.db.set_single_value("Heavy Equipment Rental Settings", "native_workflow_migrated", 1)
