"""Read APIs respect Project, Assignment, Crane and Timesheet visibility."""

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import getdate, today

from heavy_equipment_rental.rental_validation import (
	allocation_window,
	check_date_order,
	entry_days,
	interval,
	project_doc,
	ranges_overlap,
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
		"Crane", filters={"name": crane} if crane else {}, fields=["name", "crane_name"], limit_page_length=0
	)
	crane_names = {row.name: row.crane_name for row in cranes}
	if not parents or not crane_names:
		return []
	filters = {
		"parent": ["in", parents],
		"parenttype": "Crane Assignment",
		"crane": ["in", list(crane_names)],
	}
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
		row.crane_name = crane_names.get(row.crane, row.crane)
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
def crane_availability(crane, date=None, to_date=None):
	doc = frappe.get_doc("Crane", crane)
	doc.check_permission("read")
	start, end = getdate(date or today()), getdate(to_date or date or today())
	check_date_order(start, end, _("Availability period"))
	from heavy_equipment_rental.rental_validation import allocations

	all_rows = allocations([crane], lock=False)
	current = [
		r for r in all_rows if allocation_window(r) and ranges_overlap(start, end, *allocation_window(r))
	]
	future = [r for r in all_rows if r.status == "Reserved" and getdate(r.start_date) > end]
	work = frappe.db.sql(
		"""SELECT e.* FROM `tabTimesheet Entry` e JOIN `tabCrane Timesheet` s ON s.name=e.parent
		WHERE e.parenttype='Crane Timesheet' AND s.crane=%s AND s.docstatus<2
		AND e.work_date BETWEEN %s AND %s""",
		(crane, start - timedelta(days=1), end),
		as_dict=True,
	)
	has_work = any(start <= day <= end for row in work for day in entry_days(row))
	available = not current and doc.operational_condition != "Inactive"
	indicators = []
	if any(r.status == "Reserved" for r in current):
		indicators.append("Reserved for selected date")
	if has_work:
		indicators.append("Work recorded")
	if future:
		indicators.append("Upcoming reservation")
	if available:
		indicators.append("Available for selected dates")
	if doc.operational_condition != "Operational":
		indicators.append(doc.operational_condition)
	visible = {r.name for r in visible_allocations(crane=crane)}
	return {
		"date": start,
		"to_date": end,
		"operational_condition": doc.operational_condition,
		"available": available,
		"indicators": indicators,
		"work_recorded": has_work,
		"future_reservations": [r for r in future if r.name in visible],
		"has_future_reservations": bool(future),
	}


@frappe.whitelist()
def get_project_timeline(project=None, from_date=None, to_date=None, crane=None, status=None, assignment=None):
	start, end = getdate(from_date or today()), getdate(to_date or today())
	check_date_order(start, end, _("Timeline"))
	if (end - start).days > 1096:
		frappe.throw(_("Choose a timeline range of at most three years."))
	if assignment:
		assignment_doc = frappe.get_doc("Crane Assignment", assignment)
		assignment_doc.check_permission("read")
		if project and assignment_doc.project != project:
			frappe.throw(_("Assignment does not belong to the selected Project."))
		project = assignment_doc.project
	rows = visible_allocations(project, crane, status)
	if assignment:
		rows = [row for row in rows if row.parent == assignment]
	lanes = {}
	crane_names = dict(
		frappe.get_list("Crane", fields=["name", "crane_name"], limit_page_length=0, as_list=True)
	)

	def lane(name):
		return lanes.setdefault(
			name, {"crane": name, "crane_name": crane_names.get(name, name), "segments": [], "work": []}
		)

	for row in rows:
		if getdate(row.start_date) > end or getdate(row.expected_end_date) < start:
			continue
		lane(row.crane)["segments"].append(
			{
				"assignment": row.parent,
				"project": row.project,
				"row_name": row.name,
				"start_date": row.start_date,
				"end_date": row.expected_end_date,
				"row_status": row.status,
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
			fields=["name", "crane", "project", "docstatus"],
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
			if assignment and not any(
				booking.crane == sheet.crane
				and (window := allocation_window(booking))
				and window[0] <= day <= window[1]
				for booking in rows
			):
				continue
			key = sheet.crane, day
			marker = markers.setdefault(
				key,
				{
					"date": day,
					"operator_hours": 0,
					"intervals": [],
					"statuses": set(),
					"timesheets": set(),
				},
			)
			marker["statuses"].add("Submitted" if sheet.docstatus == 1 else "Draft")
			marker["timesheets"].add(sheet.name)
			first, last = interval(row)
			seconds = (
				min(last, datetime.combine(day + timedelta(days=1), time.min))
				- max(first, datetime.combine(day, time.min))
			).total_seconds()
			marker["operator_hours"] += seconds / 3600
			if seconds > 0:
				marker["intervals"].append((
					max(first, datetime.combine(day, time.min)),
					min(last, datetime.combine(day + timedelta(days=1), time.min)),
				))
	for (name, day), marker in markers.items():
		merged = []
		for first, last in sorted(marker.pop("intervals")):
			if merged and first <= merged[-1][1]:
				merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
			else:
				merged.append((first, last))
		marker["crane_hours"] = sum((last - first).total_seconds() / 3600 for first, last in merged)
		marker["date"] = str(day)
		marker["statuses"] = sorted(marker["statuses"])
		marker["timesheets"] = sorted(marker["timesheets"])
		lane(name)["work"].append(marker)
	return {"from_date": start, "to_date": end, "cranes": sorted(lanes.values(), key=lambda x: x["crane"])}
