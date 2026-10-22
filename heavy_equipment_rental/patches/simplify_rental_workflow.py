"""Preserve legacy rentals while moving active work from Crane Project to Assignment."""

import frappe
from frappe.utils import getdate


def execute():
    if not frappe.db.table_exists("Crane Project") or not all((
        frappe.db.has_column("Crane Assignment", "project"),
        frappe.db.has_column("Crane Timesheet", "project"),
    )):
        return
    projects = {row.name: row for row in frappe.db.sql(
        "SELECT name, project_name, customer, company, expected_start_date, expected_end_date "
        "FROM `tabCrane Project`", as_dict=True)}
    assignments = frappe.db.sql(
        "SELECT name, project FROM `tabCrane Assignment` WHERE project IS NOT NULL", as_dict=True)
    for assignment in assignments:
        project = projects.get(assignment.project)
        if not project:
            continue
        frappe.db.set_value("Crane Assignment", assignment.name, {
            "customer": project.customer,
            "company": project.company,
            "location": (project.project_name or project.name).strip(),
        }, update_modified=False)
    if frappe.db.has_column("Assigned Crane", "status"):
        frappe.db.sql("""UPDATE `tabAssigned Crane` SET cancelled=1
            WHERE status='Cancelled' AND parenttype='Crane Assignment'""")
    if frappe.db.has_column("Timesheet Entry", "crane_operator"):
        frappe.db.sql("""UPDATE `tabTimesheet Entry` e
            JOIN `tabCrane Driver` d ON d.name=e.crane_operator
            SET e.employee=d.employee WHERE e.parenttype='Crane Timesheet' AND d.employee IS NOT NULL""")
    sheets = frappe.db.sql("""SELECT name, project, crane, period_start, period_end, assignment
        FROM `tabCrane Timesheet` WHERE project IS NOT NULL""", as_dict=True)
    for sheet in sheets:
        project = projects.get(sheet.project)
        if not project:
            continue
        entries = frappe.db.sql("""SELECT * FROM `tabTimesheet Entry`
            WHERE parenttype='Crane Timesheet' AND parent=%s""", sheet.name, as_dict=True)
        days = {getdate(entry.work_date) for entry in entries if entry.work_date and
                entry.start_time is not None and entry.end_time is not None}
        if not days:
            days = {getdate(sheet.period_start), getdate(sheet.period_end)}
        rows = frappe.db.sql("""SELECT a.name AS assignment, r.start_date, r.expected_end_date
            FROM `tabCrane Assignment` a JOIN `tabAssigned Crane` r ON r.parent=a.name
            WHERE a.project=%s AND r.crane=%s AND COALESCE(r.cancelled,0)=0""",
            (sheet.project, sheet.crane), as_dict=True)
        candidates = sorted({row.assignment for row in rows if all(
            any(other.assignment == row.assignment and
                getdate(other.start_date) <= day <= getdate(other.expected_end_date)
                for other in rows) for day in days)})
        if sheet.assignment and frappe.db.exists("Crane Assignment", sheet.assignment):
            selected = sheet.assignment
        elif candidates:
            # Legacy records can contain duplicate assignments; keep the earliest stable link.
            selected = candidates[0]
        else:
            prices = [entry.price_per_hour for entry in entries if entry.price_per_hour]
            rate = prices[0] if prices else frappe.db.get_value(
                "Crane Period Price", {"parent": sheet.crane, "period": "Hour"}, "price") or 0
            rental = frappe.get_doc({
                "doctype": "Crane Assignment", "customer": project.customer,
                "company": project.company, "location": (project.project_name or project.name).strip(),
                "assigned_cranes": [{
                    "crane": sheet.crane,
                    "start_date": project.expected_start_date,
                    "expected_end_date": project.expected_end_date,
                    "rental_rate_unit": "Hour", "rental_rate": rate,
                }],
            })
            rental.flags.legacy_migration = True
            rental.insert(ignore_permissions=True)
            selected = rental.name
        frappe.db.set_value("Crane Timesheet", sheet.name, {
            "assignment": selected, "customer": project.customer,
            "location": (project.project_name or project.name).strip(),
        }, update_modified=False)
