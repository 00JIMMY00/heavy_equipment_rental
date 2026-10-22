"""Backfill rentals created when assignments linked ERPNext's native Project."""

import frappe
from frappe.utils import getdate


def execute():
    if not frappe.db.table_exists("Project") or not frappe.db.has_column("Crane Assignment", "project"):
        return
    rows = frappe.db.sql("""SELECT a.name, p.customer, p.company, p.project_name
        FROM `tabCrane Assignment` a JOIN `tabProject` p ON p.name=a.project
        WHERE a.customer IS NULL OR a.location IS NULL""", as_dict=True)
    for row in rows:
        frappe.db.set_value("Crane Assignment", row.name, {
            "customer": row.customer,
            "company": row.company,
            "location": (row.project_name or row.name).strip(),
        }, update_modified=False)
    if not frappe.db.has_column("Crane Timesheet", "project"):
        return
    sheets = frappe.db.sql("""SELECT s.name, s.project, s.crane, s.period_start, s.period_end,
        p.customer, p.company, p.project_name, p.expected_start_date, p.expected_end_date
        FROM `tabCrane Timesheet` s JOIN `tabProject` p ON p.name=s.project
        WHERE s.assignment IS NULL""", as_dict=True)
    for sheet in sheets:
        entries = frappe.db.sql("""SELECT work_date FROM `tabTimesheet Entry`
            WHERE parenttype='Crane Timesheet' AND parent=%s AND work_date IS NOT NULL""",
            sheet.name, as_dict=True)
        days = {getdate(entry.work_date) for entry in entries} or {
            getdate(sheet.period_start), getdate(sheet.period_end)}
        rows = frappe.db.sql("""SELECT a.name AS assignment, r.start_date, r.expected_end_date
            FROM `tabCrane Assignment` a JOIN `tabAssigned Crane` r ON r.parent=a.name
            WHERE a.project=%s AND r.crane=%s AND COALESCE(r.cancelled,0)=0""",
            (sheet.project, sheet.crane), as_dict=True)
        candidates = sorted({row.assignment for row in rows if all(
            any(other.assignment == row.assignment and
                getdate(other.start_date) <= day <= getdate(other.expected_end_date)
                for other in rows) for day in days)})
        if candidates:
            assignment = candidates[0]
        else:
            rental = frappe.get_doc({
                "doctype": "Crane Assignment", "customer": sheet.customer,
                "company": sheet.company, "location": (sheet.project_name or sheet.project).strip(),
                "assigned_cranes": [{
                    "crane": sheet.crane, "start_date": sheet.expected_start_date,
                    "expected_end_date": sheet.expected_end_date,
                    "rental_rate_unit": "Hour", "rental_rate": 0,
                }],
            })
            rental.flags.legacy_migration = True
            rental.insert(ignore_permissions=True)
            assignment = rental.name
        frappe.db.set_value("Crane Timesheet", sheet.name, {
            "assignment": assignment, "customer": sheet.customer,
            "location": (sheet.project_name or sheet.project).strip(),
        }, update_modified=False)
