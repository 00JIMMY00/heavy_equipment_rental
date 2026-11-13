"""Read-only calendar feed for rental operations."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate, get_time

from heavy_equipment_rental.rental_queries import visible_allocations


@frappe.whitelist()
def get_calendar_events(start_date, end_date):
    start, end = getdate(start_date), getdate(end_date)
    if end < start or (end - start).days > 120:
        frappe.throw(_("Choose a calendar range of at most 120 days."))
    events = []
    cranes = dict(frappe.get_list("Crane", fields=["name", "crane_name"],
                                 as_list=True, limit_page_length=0)) if frappe.has_permission("Crane", "read") else {}
    if frappe.has_permission("Crane Assignment", "read"):
        for row in visible_allocations():
            if getdate(row.start_date) > end or getdate(row.expected_end_date) < start:
                continue
            events.append({
                "id": f"reservation:{row.name}", "type": "reservation", "doctype": "Crane Assignment",
                "docname": row.parent, "title": f"{row.crane_name} · {row.customer}",
                "participant": row.crane_name, "venue": row.location,
                "fromDate": str(row.start_date), "toDate": str(row.expected_end_date),
                "isFullDay": True, "color": "blue", "status": "Booked",
                "crane": row.crane, "crane_name": row.crane_name,
                "assignment": row.parent, "assignment_name": f"{row.customer} · {row.location}",
            })
    if frappe.has_permission("Crane Timesheet", "read"):
        sheets = frappe.get_list("Crane Timesheet", filters={
            "docstatus": ["<", 2], "period_start": ["<=", end], "period_end": [">=", start]},
            fields=["name", "assignment", "crane", "customer", "location", "period_start", "period_end",
                    "docstatus", "total_crane_billable_hours"], limit_page_length=0)
        by_name = {row.name: row for row in sheets}
        entries = frappe.get_all("Timesheet Entry", filters={
            "parenttype": "Crane Timesheet", "parent": ["in", list(by_name)]},
            fields=["name", "parent", "work_date", "start_time", "end_time", "ends_next_day", "employee"],
            limit_page_length=0) if by_name else []
        seen = set()
        for entry in entries:
            if not entry.work_date or entry.start_time in (None, "") or entry.end_time in (None, ""):
                continue
            seen.add(entry.parent)
            date = getdate(entry.work_date)
            last = date + timedelta(days=1 if entry.ends_next_day else 0)
            if date > end or last < start:
                continue
            sheet = by_name[entry.parent]
            events.append({
                "id": f"timesheet:{sheet.name}:{entry.name}", "type": "timesheet",
                "doctype": "Crane Timesheet", "docname": sheet.name,
                "title": f"{cranes.get(sheet.crane, sheet.crane)} · {entry.employee or 'Work'}",
                "participant": entry.employee or "", "venue": sheet.location,
                "fromDate": str(date), "toDate": str(last),
                "fromTime": get_time(entry.start_time).strftime("%H:%M"),
                "toTime": get_time(entry.end_time).strftime("%H:%M"),
                "isFullDay": False, "color": "green",
                "status": "Submitted" if sheet.docstatus == 1 else "Draft",
                "isDraft": sheet.docstatus == 0, "crane": sheet.crane,
                "crane_name": cranes.get(sheet.crane, sheet.crane),
                "assignment": sheet.assignment, "assignment_name": f"{sheet.customer} · {sheet.location}",
            })
        for sheet in sheets:
            if sheet.name in seen:
                continue
            events.append({
                "id": f"timesheet:{sheet.name}", "type": "timesheet", "doctype": "Crane Timesheet",
                "docname": sheet.name, "title": f"Timesheet {sheet.name}",
                "participant": cranes.get(sheet.crane, sheet.crane), "venue": sheet.location,
                "fromDate": str(sheet.period_start), "toDate": str(sheet.period_end),
                "isFullDay": True, "color": "green",
                "status": "Submitted" if sheet.docstatus == 1 else "Draft",
                "isDraft": sheet.docstatus == 0, "crane": sheet.crane,
                "crane_name": cranes.get(sheet.crane, sheet.crane),
                "assignment": sheet.assignment, "assignment_name": f"{sheet.customer} · {sheet.location}",
            })
    if frappe.has_permission("Crane Maintenance", "read"):
        rows = frappe.get_list("Crane Maintenance", fields=[
            "name", "crane", "maintenance_type", "status", "technician", "planned_start_date",
            "planned_end_date", "actual_start_date", "actual_end_date"], limit_page_length=0)
        for row in rows:
            for phase, first, last in (("planned", row.planned_start_date, row.planned_end_date),
                                       ("actual", row.actual_start_date, row.actual_end_date)):
                last = last or first
                if not first or getdate(first) > end or getdate(last) < start:
                    continue
                if phase == "actual" and first == row.planned_start_date and last == (row.planned_end_date or first):
                    continue
                events.append({
                    "id": f"maintenance:{row.name}:{phase}", "type": "maintenance",
                    "doctype": "Crane Maintenance", "docname": row.name,
                    "title": f"{phase.title()} {row.maintenance_type or 'maintenance'} · {cranes.get(row.crane, row.crane)}",
                    "participant": row.technician or "", "fromDate": str(first), "toDate": str(last),
                    "isFullDay": True, "color": "orange", "status": row.status,
                    "phase": phase, "crane": row.crane, "crane_name": cranes.get(row.crane, row.crane),
                })
    return events


@frappe.whitelist()
def get_resource_calendar_data(start_date, end_date):
    events = get_calendar_events(start_date, end_date)
    resources = []
    if frappe.has_permission("Crane", "read"):
        resources = [{"id": f"crane:{row.name}", "title": row.crane_name or row.name,
                      "group": "Fleet", "detail": row.model or row.operational_condition or row.name}
                     for row in frappe.get_list("Crane", fields=["name", "crane_name", "model", "operational_condition"],
                                                limit_page_length=0)]
    return {"events": events, "resources": resources}
