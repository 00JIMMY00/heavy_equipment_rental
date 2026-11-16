"""Rename the rental DocType in place, retaining IDs and all linked work."""
import frappe


def execute():
    if frappe.db.exists('DocType', 'Crane Assignment') and not frappe.db.exists('DocType', 'Rental Contract'):
        frappe.rename_doc('DocType', 'Crane Assignment', 'Rental Contract', force=True, show_alert=False)
