"""Read-only calendar feed for reservations, projects, and timesheets."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate, get_time


@frappe.whitelist()
def get_calendar_events(start_date, end_date):
    start, end = getdate(start_date), getdate(end_date)
    if end < start or (end - start).days > 120:
        frappe.throw(_("Choose a calendar range of at most 120 days."))

    events = []
    projects = {}
    if frappe.has_permission("Crane Project", "read"):
        project_rows = frappe.get_list(
            "Crane Project",
            filters={"expected_start_date": ["<=", end], "expected_end_date": [">=", start]},
            fields=["name", "project_name", "customer", "status", "expected_start_date", "expected_end_date"],
            limit_page_length=0,
        )
        projects = {row.name: row for row in project_rows}
        for row in project_rows:
            events.append({
                "id": f"project:{row.name}", "type": "project", "doctype": "Crane Project", "docname": row.name,
                "title": row.project_name or row.name, "participant": row.customer or "",
                "fromDate": str(row.expected_start_date), "toDate": str(row.expected_end_date),
                "isFullDay": True, "color": "violet", "status": row.status,
                "isDeclined": row.status == "Cancelled",
            })

    # Only show child allocations whose parent assignment and project are both visible.
    if projects and frappe.has_permission("Crane Assignment", "read"):
        assignments = frappe.get_list(
            "Crane Assignment", filters={"project": ["in", list(projects)]},
            fields=["name", "project"], limit_page_length=0,
        )
        by_assignment = {row.name: row.project for row in assignments}
        if by_assignment:
            rows = frappe.get_all(
                "Assigned Crane",
                filters={"parenttype": "Crane Assignment", "parent": ["in", list(by_assignment)],
                         "start_date": ["<=", end], "expected_end_date": [">=", start]},
                fields=["name", "parent", "crane", "crane_driver", "start_date", "expected_end_date", "status"],
                limit_page_length=0,
            )
            crane_names = dict(frappe.get_list("Crane", fields=["name", "crane_name"], as_list=True, limit_page_length=0)) if frappe.has_permission("Crane", "read") else {}
            for row in rows:
                project = projects[by_assignment[row.parent]]
                crane_name = crane_names.get(row.crane, row.crane)
                events.append({
                    "id": f"reservation:{row.name}", "type": "reservation", "doctype": "Crane Assignment",
                    "docname": row.parent, "title": f"{crane_name} · {project.project_name or project.name}",
                    "participant": row.crane_driver or "", "venue": project.customer or "",
                    "fromDate": str(row.start_date), "toDate": str(row.expected_end_date),
                    "isFullDay": True, "color": "blue" if row.status == "Reserved" else "amber",
                    "status": row.status, "crane": row.crane, "project": project.name,
                    "isDraft": row.status == "Draft", "isDeclined": row.status == "Cancelled",
                })

    if frappe.has_permission("Crane Timesheet", "read"):
        sheets = frappe.get_list(
            "Crane Timesheet",
            filters={"docstatus": ["<", 2], "period_start": ["<=", end], "period_end": [">=", start]},
            fields=["name", "project", "crane", "period_start", "period_end", "docstatus", "total_crane_billable_hours"],
            limit_page_length=0,
        )
        by_name = {row.name: row for row in sheets}
        entries = frappe.get_all(
            "Timesheet Entry",
            filters={"parenttype": "Crane Timesheet", "parent": ["in", list(by_name)]},
            fields=["name", "parent", "work_date", "start_time", "end_time", "ends_next_day", "crane_operator"],
            limit_page_length=0,
        ) if by_name else []
        sheets_with_entries = set()
        crane_ids = list({row.crane for row in sheets if row.crane})
        driver_ids = list({row.crane_operator for row in entries if row.crane_operator})
        cranes = {row.name: row.crane_name for row in frappe.get_list(
            "Crane", filters={"name": ["in", crane_ids]}, fields=["name", "crane_name"], limit_page_length=0,
        )} if crane_ids and frappe.has_permission("Crane", "read") else {}
        drivers = {row.name: row.operator_name for row in frappe.get_list(
            "Crane Driver", filters={"name": ["in", driver_ids]}, fields=["name", "operator_name"], limit_page_length=0,
        )} if driver_ids and frappe.has_permission("Crane Driver", "read") else {}
        for entry in entries:
            if not entry.work_date or entry.start_time in (None, "") or entry.end_time in (None, ""):
                continue
            sheets_with_entries.add(entry.parent)
            work_date = getdate(entry.work_date)
            last_date = work_date + timedelta(days=1 if entry.ends_next_day else 0)
            if work_date > end or last_date < start:
                continue
            sheet = by_name[entry.parent]
            events.append({
                "id": f"timesheet:{sheet.name}:{entry.name}", "type": "timesheet",
                "doctype": "Crane Timesheet", "docname": sheet.name,
                "title": f"{cranes.get(sheet.crane, sheet.crane)} · {drivers.get(entry.crane_operator, entry.crane_operator or 'Work')}",
                "participant": drivers.get(entry.crane_operator, entry.crane_operator or ""), "venue": sheet.project or "",
                "fromDate": str(work_date), "toDate": str(last_date),
                "fromTime": get_time(entry.start_time).strftime("%H:%M"),
                "toTime": get_time(entry.end_time).strftime("%H:%M"),
                "isFullDay": False, "color": "green",
                "status": "Submitted" if sheet.docstatus == 1 else "Draft",
                "isDraft": sheet.docstatus == 0, "crane": sheet.crane, "project": sheet.project,
            })
        for row in sheets:
            if row.name in sheets_with_entries:
                continue
            # Empty draft timesheets still appear as a planning window.
            events.append({
                "id": f"timesheet:{row.name}", "type": "timesheet", "doctype": "Crane Timesheet",
                "docname": row.name, "title": f"Timesheet {row.name}",
                "participant": row.crane or "", "venue": row.project or "",
                "fromDate": str(row.period_start), "toDate": str(row.period_end),
                "isFullDay": True, "color": "green", "status": "Submitted" if row.docstatus == 1 else "Draft",
                "isDraft": row.docstatus == 0, "hours": row.total_crane_billable_hours,
                "crane": row.crane, "project": row.project,
            })
    return events


@frappe.whitelist()
def get_resource_calendar_data(start_date, end_date):
    """Use the same permission-filtered events as the Frappe UI calendar."""
    events = get_calendar_events(start_date, end_date)
    resources = []
    if frappe.has_permission("Crane Project", "read"):
        project_ids = list({event["docname"] for event in events if event["type"] == "project"})
        if project_ids:
            projects = frappe.get_list(
                "Crane Project", filters={"name": ["in", project_ids]},
                fields=["name", "project_name", "customer"], limit_page_length=0,
            )
            resources.extend({
                "id": f"project:{row.name}", "title": row.project_name or row.name,
                "group": "Projects", "detail": row.customer or row.name,
            } for row in projects)
    if frappe.has_permission("Crane", "read"):
        cranes = frappe.get_list(
            "Crane", fields=["name", "crane_name", "model", "operational_condition"],
            limit_page_length=0,
        )
        resources.extend({
            "id": f"crane:{row.name}", "title": row.crane_name or row.name,
            "group": "Fleet", "detail": row.model or row.operational_condition or row.name,
        } for row in cranes)
    return {"events": events, "resources": resources}
