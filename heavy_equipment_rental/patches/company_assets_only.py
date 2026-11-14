"""Derive company-only recognition; archive obsolete links without touching ledgers."""

import json

import frappe
from heavy_equipment_rental.crane_assets import accounting_basis, company_ownership_percentage


def execute():
	for name in frappe.get_all("Crane", pluck="name"):
		crane = frappe.get_doc("Crane", name)
		basis = accounting_basis(crane)
		values = dict(asset_accounting_basis=basis)
		obsolete = crane.asset and (not basis or
			(crane.asset_accounting_basis == "Whole Crane" and company_ownership_percentage(crane) < 100))
		if obsolete:
			history = json.loads(crane.legacy_asset_recognition or "[]")
			history.append(dict(asset=crane.asset, basis=crane.asset_accounting_basis,
				ownership_type=crane.ownership_type, reason="Company-only asset recognition"))
			values.update(asset=None, legacy_asset_recognition=json.dumps(history))
		frappe.db.set_value("Crane", name, values, update_modified=False)
