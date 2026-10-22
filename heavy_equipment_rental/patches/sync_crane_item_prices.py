"""Add the read-only Item price table and copy prices from existing Cranes."""

import frappe

from heavy_equipment_rental.item_prices import install_item_price_field, sync_crane_item_prices


def execute():
	install_item_price_field()
	for name in frappe.get_all("Crane", pluck="name", limit_page_length=0):
		sync_crane_item_prices(frappe.get_doc("Crane", name))
