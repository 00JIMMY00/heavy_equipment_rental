"""Read APIs respect Project, Assignment, Crane and Timesheet visibility."""

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from jimmy_cranes.rental_validation import (
	allocation_window,
	check_date_order,
	entry_days,
	interval,
	project_doc,
)


def visible_allocations(project=None, crane=None, status=None):
	if project:
		project_doc(project)
	projects = frappe.get_list(
		"Crane Project", filters={"name": project} if project else {}, pluck="name", limit_page_length=0
	)
	if not projects:
		return []
	parents = frappe.get_list(
		"Crane Assignment", filters={"project": ["in", projects]}, pluck="name", limit_page_length=0
	)
	cranes = frappe.get_list(
		"Crane", filters={"name": crane} if crane else {}, pluck="name", limit_page_length=0
	)
	if not parents or not cranes:
		return []
	filters = {"parent": ["in", parents], "parenttype": "Crane Assignment", "crane": ["in", cranes]}
	if status:
		filters["status"] = status
	rows = frappe.get_all("Assigned Crane", filters=filters, fields=["*"], order_by="crane,start_date,idx")
	mapping = dict(
		frappe.get_all(
			"Crane Assignment", filters={"name": ["in", parents]}, fields=["name", "project"], as_list=True
		)
	)
	for row in rows:
		row.assignment, row.project = row.parent, mapping[row.parent]
	return rows


@frappe.whitelist()
def project_overview(project):
	return visible_allocations(project=project)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def assigned_crane_query(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	if not filters.get("project"):
		return []
	date = getdate(filters.get("work_date") or today())
	names = {
		r.crane
		for r in visible_allocations(project=filters["project"])
		if allocation_window(r) and allocation_window(r)[0] <= date <= allocation_window(r)[1]
	}
	if not names:
		return []
	return frappe.get_list(
		"Crane",
		filters={"name": ["in", list(names)]},
		or_filters={"name": ["like", "%" + txt + "%"], "crane_name": ["like", "%" + txt + "%"]},
		fields=["name", "crane_name"],
		start=start,
		page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def crane_availability(crane, date=None):
	doc = frappe.get_doc("Crane", crane)
	doc.check_permission("read")
	day = getdate(date or today())
	# The availability boolean must consider hidden bookings too. Only expose
	# links/details to assignments the caller can read.
	from jimmy_cranes.rental_validation import allocations

	all_rows = allocations([crane], lock=False)
	current = [
		r
		for r in all_rows
		if allocation_window(r) and allocation_window(r)[0] <= day <= allocation_window(r)[1]
	]
	future = [r for r in all_rows if allocation_window(r) and allocation_window(r)[0] > day]
	activity = (
		"Working"
		if any(
			(r.status == "In Progress" and (not r.actual_start_date or getdate(r.actual_start_date) <= day))
			or (r.status == "Complete" and r.actual_start_date and getdate(r.actual_start_date) <= day)
			for r in current
		)
		else "Reserved"
		if current
		else "Idle"
	)
	visible = {r.name for r in visible_allocations(crane=crane)}
	return {
		"date": day,
		"operational_condition": doc.operational_condition,
		"activity": activity,
		"available": not current and doc.operational_condition == "Operational",
		"explanation": doc.operational_condition
		if doc.operational_condition != "Operational"
		else "Allocated on this date"
		if current
		else "No allocation on this date",
		"future_reservations": [r for r in future if r.name in visible],
		"has_future_reservations": bool(future),
	}


@frappe.whitelist()
def get_project_timeline(project=None, from_date=None, to_date=None, crane=None, status=None):
	start, end = getdate(from_date or today()), getdate(to_date or today())
	check_date_order(start, end, _("Timeline"))
	if (end - start).days > 1096:
		frappe.throw(_("Choose a timeline range of at most three years."))
	rows = visible_allocations(project, crane, status)
	lanes = {}
	crane_names = dict(
		frappe.get_list("Crane", fields=["name", "crane_name"], limit_page_length=0, as_list=True)
	)

	def lane(name):
		return lanes.setdefault(
			name, {"crane": name, "crane_name": crane_names.get(name, name), "segments": [], "work": []}
		)

	for row in rows:
		if (
			getdate(row.start_date) > end
			or max(getdate(row.expected_end_date), getdate(row.actual_end_date or row.expected_end_date))
			< start
		):
			continue
		lane(row.crane)["segments"].append(
			{
				"assignment": row.parent,
				"project": row.project,
				"row_name": row.name,
				"start_date": row.start_date,
				"end_date": row.expected_end_date,
				"effective_end_date": (allocation_window(row) or (None, None))[1],
				"actual_start_date": row.actual_start_date,
				"actual_end_date": row.actual_end_date,
				"row_status": row.status,
				"unknown_actual_dates": bool(row.legacy_needs_review),
			}
		)
	visible_projects = frappe.get_list(
		"Crane Project", filters={"name": project} if project else {}, pluck="name", limit_page_length=0
	)
	sheets = []
	if visible_projects:
		filters = {
			"project": ["in", visible_projects],
			"docstatus": ["<", 2],
			"period_start": ["<=", end],
			"period_end": [">=", start],
		}
		if crane:
			filters["crane"] = crane
		sheets = frappe.get_list(
			"Crane Timesheet",
			filters=filters,
			fields=["name", "crane", "project", "docstatus", "legacy_needs_review", "legacy_source_status"],
			limit_page_length=0,
		)
	sheets = {s.name: s for s in sheets if s.crane in crane_names and (not status or s.crane in lanes)}
	entries = (
		frappe.get_all(
			"Timesheet Entry",
			filters={"parent": ["in", list(sheets)], "parenttype": "Crane Timesheet"},
			fields=["*"],
		)
		if sheets
		else []
	)
	markers = {}
	for row in entries:
		sheet = sheets[row.parent]
		for day in entry_days(row):
			if not start <= day <= end:
				continue
			key = sheet.crane, day
			marker = markers.setdefault(
				key,
				{
					"date": day,
					"operator_hours": 0,
					"statuses": set(),
					"timesheets": set(),
					"legacy_unknown_hours": False,
					"legacy_reported_hours": 0,
				},
			)
			marker["statuses"].add("Submitted" if sheet.docstatus == 1 else "Draft")
			if sheet.legacy_source_status:
				marker["statuses"].add("Legacy " + sheet.legacy_source_status)
			marker["timesheets"].add(sheet.name)
			if row.start_time is None or row.end_time is None:
				marker["legacy_unknown_hours"] = True
				marker["legacy_reported_hours"] += flt(row.get("working_hours")) + flt(
					row.get("overtime_hours")
				)
			else:
				first, last = interval(row)
				seconds = (
					min(last, datetime.combine(day + timedelta(days=1), time.min))
					- max(first, datetime.combine(day, time.min))
				).total_seconds()
				marker["operator_hours"] += seconds / 3600
	for (name, day), marker in markers.items():
		marker["date"] = str(day)
		marker["statuses"] = sorted(marker["statuses"])
		marker["timesheets"] = sorted(marker["timesheets"])
		lane(name)["work"].append(marker)
	return {"from_date": start, "to_date": end, "cranes": sorted(lanes.values(), key=lambda x: x["crane"])}
