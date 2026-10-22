"""Show Crane reference prices on its linked ERPNext Item."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install_item_price_field():
	create_custom_fields({"Item": [
		{
			"fieldname": "crane_prices_section",
			"fieldtype": "Section Break",
			"label": "Crane Period Prices",
			"insert_after": "standard_rate",
			"depends_on": "eval:doc.item_code && doc.item_code.startsWith('CRANE-')",
		},
		{
			"fieldname": "period_prices",
			"fieldtype": "Table",
			"label": "Period Prices",
			"options": "Crane Period Price",
			"insert_after": "crane_prices_section",
			"read_only": 1,
			"depends_on": "eval:doc.item_code && doc.item_code.startsWith('CRANE-')",
		},
	]})


def sync_crane_item_prices(crane):
	if not crane.item:
		return
	item = frappe.get_doc("Item", crane.item)
	prices = [(row.period, row.price) for row in crane.period_prices]
	if [(row.period, row.price) for row in item.get("period_prices", [])] == prices:
		return
	item.set("period_prices", [
		{"period": period, "price": price} for period, price in prices
	])
	item.save(ignore_permissions=True)
