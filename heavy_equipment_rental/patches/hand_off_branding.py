"""Replace only this app's old branding with the base theme's defaults."""

import frappe


def execute():
	for doctype, fieldname in (
		("Navbar Settings", "app_logo"),
		("Website Settings", "app_logo"),
		("Website Settings", "favicon"),
		("Website Settings", "splash_image"),
		("Website Settings", "app_name"),
	):
		current = frappe.db.get_single_value(doctype, fieldname) or ""
		if current.startswith("/assets/heavy_equipment_rental/branding/") or (
			fieldname == "app_name" and current == "Heavy Equipment Rental"
		):
			frappe.db.set_single_value(doctype, fieldname, "")
	from arab_erp_theme.branding import apply_branding
	apply_branding()
