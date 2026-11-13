import json

import frappe


def execute():
	for row in frappe.get_all("Crane", filters={"settlement_revenue_basis": ["is", "not set"]},
		fields=["name", "agreement_history"]):
		history = json.loads(row.agreement_history or "[]")
		basis = history[-1].get("settlement_revenue_basis", "Invoice Grand Total") if history else "Net Revenue"
		frappe.db.set_value("Crane", row.name, "settlement_revenue_basis", basis, update_modified=False)
