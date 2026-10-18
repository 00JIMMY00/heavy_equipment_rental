"""Make the rental workspace the starting workspace for its users."""

import frappe


def execute():
	if not frappe.db.exists("Workspace", "Crane Operations"):
		return
	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", ["System Manager", "Projects Manager", "Projects User"]], "parenttype": "User"},
		pluck="parent",
	)
	for user in set(users):
		if user != "Guest" and frappe.db.exists("User", user) and not frappe.db.get_value("User", user, "default_workspace"):
			frappe.db.set_value("User", user, "default_workspace", "Crane Operations", update_modified=False)
