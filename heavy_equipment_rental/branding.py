"""App branding defaults for sites that still use Frappe/ERPNext artwork."""

import frappe

ICON = "/assets/heavy_equipment_rental/branding/ar-monogram-classic.png"
FAVICON = "/assets/heavy_equipment_rental/branding/favicon-classic.ico"
LEGACY_BRANDING = (
	"/assets/heavy_equipment_rental/branding/ar-monogram.png",
	"/assets/heavy_equipment_rental/branding/favicon.ico",
	"/assets/heavy_equipment_rental/branding/ar-monogram-glass.png",
	"/assets/heavy_equipment_rental/branding/favicon-glass.ico",
)
APP_NAME = "Heavy Equipment Rental"


def apply_branding():
	defaults = {
		"Navbar Settings": {"app_logo": ICON},
		"Website Settings": {
			"app_logo": ICON,
			"favicon": FAVICON,
			"splash_image": ICON,
			"app_name": APP_NAME,
		},
	}
	for doctype, fields in defaults.items():
		for fieldname, value in fields.items():
			current = frappe.db.get_single_value(doctype, fieldname)
			if current == value:
				continue
			if current and not (
				current.startswith(("/assets/frappe/", "/assets/erpnext/"))
				or current in LEGACY_BRANDING
				or (fieldname == "app_name" and current in ("Frappe", "ERPNext"))
			):
				continue
			frappe.db.set_single_value(doctype, fieldname, value)
