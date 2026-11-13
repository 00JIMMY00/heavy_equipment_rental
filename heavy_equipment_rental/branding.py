"""HER visual identity, kept separate from rental setup and the shared theme app."""

import frappe

ASSET_ROOT = "/assets/heavy_equipment_rental/branding/"


def apply_branding():
	"""Replace framework/base-theme defaults; retain unrelated custom site branding.

	Only presentation settings are touched. This can be run independently of
	setup/migrate, without syncing workspaces, permissions, or rental documents.
	"""
	settings = {
		"Navbar Settings": {"app_logo": ASSET_ROOT + "mobile-crane-logo.png"},
		"Website Settings": {
			"app_logo": ASSET_ROOT + "mobile-crane-logo.png",
			"favicon": ASSET_ROOT + "favicon.ico",
			"splash_image": ASSET_ROOT + "loader.gif",
			"app_name": "Heavy Equipment Rental",
		},
	}
	changed = False
	for doctype, fields in settings.items():
		for fieldname, value in fields.items():
			current = frappe.db.get_single_value(doctype, fieldname)
			if current == value:
				continue
			if current and not (
				current.startswith((
					"/assets/frappe/", "/assets/erpnext/", "/assets/arab_erp_theme/", ASSET_ROOT,
				))
				or (fieldname == "app_name" and current in ("Frappe", "ERPNext", "Arab ERP"))
			):
				continue
			frappe.db.set_single_value(doctype, fieldname, value)
			changed = True
	if changed:
		frappe.clear_cache()
