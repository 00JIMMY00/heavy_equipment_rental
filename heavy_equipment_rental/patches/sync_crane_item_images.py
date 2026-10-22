"""Backfill Item images from linked Cranes without touching unrelated Items."""

import frappe

from heavy_equipment_rental.item_prices import sync_crane_item_prices


def execute():
	for name in frappe.get_all("Crane", pluck="name", limit_page_length=0):
		sync_crane_item_prices(frappe.get_doc("Crane", name))
