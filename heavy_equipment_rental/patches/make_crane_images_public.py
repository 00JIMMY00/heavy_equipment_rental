"""Move existing private Crane images to public files for sidebar display."""

import frappe


def execute():
	for crane in frappe.get_all("Crane", fields=["name", "crane_image"], limit_page_length=0):
		if not (crane.crane_image or "").startswith("/private/files/"):
			continue
		files = frappe.get_all(
			"File", filters={"file_url": crane.crane_image, "is_private": 1},
			fields=["name", "attached_to_doctype", "attached_to_name"], limit_page_length=0,
		)
		files.sort(key=lambda row: row.attached_to_doctype != "Crane" or row.attached_to_name != crane.name)
		if not files:
			continue
		file = frappe.get_doc("File", files[0].name)
		file.is_private = 0
		file.save(ignore_permissions=True)
		frappe.db.set_value("Crane", crane.name, "crane_image", file.file_url, update_modified=False)
