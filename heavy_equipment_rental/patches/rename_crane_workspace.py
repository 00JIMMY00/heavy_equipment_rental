"""Give the crane workspace one stable English route."""

import frappe


def execute():
	new_name = "Crane Operations"
	old_names = frappe.get_all(
		"Workspace",
		filters={"name": ["in", ["Heavy Equipment Rental", "Heavy Equipment Rentalff"]]},
		pluck="name",
	)
	for old_name in old_names:
		if old_name == new_name:
			continue
		if not frappe.db.exists("Workspace", new_name):
			frappe.rename_doc("Workspace", old_name, new_name, force=True)
		else:
			frappe.delete_doc("Workspace", old_name, force=True)
	if frappe.db.exists("Workspace", new_name):
		frappe.db.set_value("Workspace", new_name, {"title": new_name, "label": new_name}, update_modified=False)
		frappe.db.sql(
			"""UPDATE `tabUser` SET default_workspace = %s
			WHERE default_workspace IN %s""",
			(new_name, tuple([*old_names, "Heavy Equipment Rental"])),
		)
		frappe.clear_cache()
