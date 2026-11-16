"""Turn saved rental location text into native Location links without repricing work."""
import frappe


def execute():
    doctypes = ("Rental Contract", "Crane Timesheet")
    locations = set()
    for doctype in doctypes:
        locations.update(frappe.db.sql(f"SELECT DISTINCT location FROM `tab{doctype}` WHERE COALESCE(location, '') != ''", pluck=True))
    for value in sorted(locations):
        name = value
        if not frappe.db.exists("Location", value):
            existing = frappe.db.get_value("Location", {"location_name": value.strip()}, "name")
            name = existing or frappe.get_doc({"doctype": "Location", "location_name": value}).insert(ignore_permissions=True).name
        if name != value:
            for doctype in doctypes:
                frappe.db.sql(f"UPDATE `tab{doctype}` SET location=%s WHERE location=%s", (name, value))
