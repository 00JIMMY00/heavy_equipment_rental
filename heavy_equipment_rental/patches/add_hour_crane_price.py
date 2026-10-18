"""Add the new Hour price to cranes created before the field was available."""

import frappe


def execute():
	for crane in frappe.get_all("Crane", pluck="name"):
		if frappe.db.exists("Crane Period Price", {"parent": crane, "parenttype": "Crane", "period": "Hour"}):
			continue
		frappe.get_doc({
			"doctype": "Crane Period Price",
			"parent": crane,
			"parenttype": "Crane",
			"parentfield": "period_prices",
			"idx": 4,
			"period": "Hour",
			"price": 0,
		}).db_insert()
