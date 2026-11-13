"""Preserve signed Timesheet uploads in the renamed attachment field."""

import frappe


def execute():
    if not (frappe.db.has_column("Crane Timesheet", "signed_timesheet")
            and frappe.db.has_column("Crane Timesheet", "attachment")):
        return
    frappe.db.sql("""UPDATE `tabCrane Timesheet`
        SET attachment=signed_timesheet
        WHERE (attachment IS NULL OR attachment='')
        AND signed_timesheet IS NOT NULL AND signed_timesheet!=''""")
    frappe.db.sql("""UPDATE `tabFile` f
        JOIN `tabCrane Timesheet` s ON s.name=f.attached_to_name
        SET f.attached_to_field='attachment'
        WHERE f.attached_to_doctype='Crane Timesheet'
        AND f.attached_to_field='signed_timesheet'
        AND f.file_url=s.attachment""")
