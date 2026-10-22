"""Populate the list thumbnail URL without marking Attach Image as a list field."""

import frappe


def execute():
	for crane in frappe.get_all("Crane", fields=["name", "crane_image"], limit_page_length=0):
		frappe.db.set_value(
			"Crane", crane.name, "crane_list_image", crane.crane_image,
			update_modified=False,
		)
