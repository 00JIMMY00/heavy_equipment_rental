"""Fill driver names and hours summaries on existing Timesheets."""

from collections import defaultdict

import frappe


def execute():
    frappe.db.sql("""UPDATE `tabTimesheet Entry` e
        JOIN `tabEmployee` d ON d.name=e.employee
        SET e.driver_name=d.employee_name
        WHERE e.parenttype='Crane Timesheet'""")
    totals = frappe.db.sql("""SELECT e.parent, e.employee, d.employee_name,
            SUM(COALESCE(e.worked_hours, 0)) AS total_hours
        FROM `tabTimesheet Entry` e
        JOIN `tabEmployee` d ON d.name=e.employee
        WHERE e.parenttype='Crane Timesheet'
        GROUP BY e.parent, e.employee, d.employee_name
        ORDER BY e.parent, MIN(e.idx)""", as_dict=True)
    by_sheet = defaultdict(list)
    for row in totals:
        by_sheet[row.parent].append(row)
    for name, rows in by_sheet.items():
        if frappe.db.exists("Driver Hours", {"parent": name, "parenttype": "Crane Timesheet"}):
            continue
        sheet = frappe.get_doc("Crane Timesheet", name)
        for row in rows:
            summary = sheet.append("driver_hours", {
                "employee": row.employee,
                "driver_name": row.employee_name,
                "total_hours": row.total_hours,
            })
            summary.db_insert()
