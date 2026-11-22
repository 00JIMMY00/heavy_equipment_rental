from collections import defaultdict
from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, getdate

from heavy_equipment_rental.fleet_operations import (
	DAY,
	bookings_by_crane,
	column,
	days_in_period,
	merged_windows,
	repair_end,
	repairs_in_period,
	report_period,
	visible_fleet,
)
from heavy_equipment_rental.rental_validation import entry_days


def submitted_days(cranes, start, end, documents=None):
	worked, recorded = defaultdict(set), defaultdict(set)
	if not cranes or end < start:
		return worked, recorded
	fields = ["work_date", "worked_hours", "overtime_hours", "start_time", "end_time", "ends_next_day"]
	entries = frappe.get_list(
		"Crane Timesheet",
		fields=["name", "crane", *["timesheet_entries." + f for f in fields]],
		filters=[
			["Crane Timesheet", "crane", "in", cranes],
			["Crane Timesheet", "docstatus", "=", 1],
			["Timesheet Entry", "work_date", "between", [start - DAY, end]],
		],
		limit_page_length=0,
	)
	for row in entries:
		for day in entry_days(row):
			if start <= day <= end:
				recorded[row.crane].add(day)
				if documents is not None:
					documents[day].add(("Crane Timesheet", row.name))
				legacy_clock_hours = (
					row.worked_hours is None and row.start_time is not None and row.end_time is not None
				)
				if legacy_clock_hours or flt(row.worked_hours) > 0 or flt(row.overtime_hours) > 0:
					worked[row.crane].add(day)
	return worked, recorded


def next_free_window(windows, first):
	for start, end in windows:
		if start > first:
			return first, start - DAY
		if end >= first:
			if end == date.max:
				return None, None
			first = end + DAY
	return first, None


def fleet_rows(start, end, as_of, crane=None):
	for source in ("Crane", "Rental Contract", "Crane Timesheet", "Crane Maintenance"):
		frappe.has_permission(source, "read", throw=True)
	fleet = visible_fleet(crane)
	names = [row.name for row in fleet]
	bookings = bookings_by_crane(crane, min(start, as_of))
	worked, recorded = submitted_days(names, start, min(end, as_of))
	planning_start = max(start, as_of)
	# A dispatcher may see the crane without being able to read every contract.
	# Suppress its forecast when the visible reservations do not cover its schedule.
	counts = (
		frappe.get_all(
			"Assigned Crane",
			filters={
				"parenttype": "Rental Contract",
				"cancelled": 0,
				"crane": ["in", names],
				"expected_end_date": [">=", planning_start],
			},
			fields=["crane", "count(name) as total"],
			group_by="crane",
			order_by="crane",
		)
		if names
		else []
	)
	scheduled = {r.crane: r.total for r in counts}
	maintenance, unavailable = defaultdict(list), defaultdict(list)
	for job in repairs_in_period(names, min(start, as_of)):
		first = getdate(job.actual_start_date)
		last = repair_end(job, as_of)
		if first <= last:
			maintenance[job.crane].append((first, last))
		unavailable[job.crane].append((first, date.max if job.status == "In Progress" else last))

	rows = []
	elapsed_end = min(end, as_of - DAY)
	for unit in fleet:
		name = unit.name
		reserved = merged_windows((b.start_date, b.expected_end_date) for b in bookings[name])

		def elapsed_booked(day):
			return day <= elapsed_end and any(first <= day <= last for first, last in reserved)

		elapsed = days_in_period(reserved, start, elapsed_end)
		operating = sum(elapsed_booked(day) for day in worked[name])
		missing = elapsed - sum(elapsed_booked(day) for day in recorded[name])
		repair_windows = merged_windows(maintenance[name])
		free_from, free_through = None, None
		visible_count = sum(b.expected_end_date >= planning_start for b in bookings[name])
		if unit.operational_condition == "Operational" and visible_count == scheduled.get(name, 0):
			free_from, free_through = next_free_window(
				merged_windows(reserved + unavailable[name]), planning_start
			)
		rows.append(
			dict(
				crane=name,
				crane_name=unit.crane_name or name,
				condition=_(unit.operational_condition or "Unspecified"),
				booked_days=days_in_period(reserved, start, end),
				elapsed_days=elapsed,
				worked_days=len(worked[name]),
				elapsed_worked=operating,
				downtime_days=len(recorded[name] - worked[name]),
				missing_days=missing,
				maintenance_days=days_in_period(repair_windows, start, min(as_of, end)),
				utilization=100 * operating / elapsed if elapsed else None,
				free_from=free_from,
				free_through=free_through,
			)
		)
	return rows


def fleet_totals(rows):
	elapsed = sum(row["elapsed_days"] for row in rows)
	operating = sum(row["elapsed_worked"] for row in rows)
	return dict(
		utilization=round(100 * operating / elapsed, 1) if elapsed else None,
		missing_days=sum(row["missing_days"] for row in rows),
	)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	start, end = report_period(filters)
	rows = fleet_rows(start, end, getdate(), filters.crane)
	columns = [
		column("crane_name", "Crane", "Data", 200),
		column("condition", "Current Condition", "Data", 165),
		column("utilization", "Booked Utilization", "Percent", 180),
		column("booked_days", "Booked Days", "Int", 135),
		column("elapsed_days", "Elapsed Booked Days", "Int", 195),
		column("worked_days", "Worked Days", "Int", 135),
		column("downtime_days", "Recorded Downtime Days", "Int", 220),
		column("missing_days", "Missing Timesheet Days", "Int", 210),
		column("maintenance_days", "Maintenance Days", "Int", 170),
		column("free_from", "Next Free From", "Date", 150),
		column("free_through", "Free Through", "Date", 140),
	]
	totals = fleet_totals(rows)
	summary = [
		dict(
			label=_("Missing Timesheet Days"),
			value=totals["missing_days"],
			datatype="Int",
			indicator="Orange",
		)
	]
	if totals["utilization"] is not None:
		summary.insert(
			0,
			dict(
				label=_("Booked Utilization"),
				value=totals["utilization"],
				datatype="Percent",
				indicator="Blue",
			),
		)
	message = _(
		"Utilization uses booked crane-days through yesterday. Only submitted shifts confirm work or downtime. "
		"Free dates use the visible schedule from today or the selected start, whichever is later. "
		"Free From stays blank for unavailable cranes or incomplete schedules. A blank Free Through on a free crane means no later booking."
	)
	chart = None
	if rows:
		fields = [c["fieldname"] for c in columns if c["fieldtype"] == "Int"]
		total = {field: sum(row[field] for row in rows) for field in fields}
		total["elapsed_worked"] = sum(row["elapsed_worked"] for row in rows)
		total.update(crane_name=_("Total"), utilization=totals["utilization"], is_total=True)
		rows.append(total)
		counts = [
			total["elapsed_worked"],
			total["elapsed_days"] - total["elapsed_worked"] - total["missing_days"],
			total["missing_days"],
		]
		if any(counts):
			chart = dict(
				type="donut",
				title=_("Elapsed Booked Days"),
				colors=["#35956b", "#787db7", "#db9235"],
				data=dict(
					labels=[_("Worked Days"), _("Recorded Downtime Days"), _("Missing Timesheet Days")],
					datasets=[dict(values=counts)],
				),
			)
	return columns, rows, message, chart, summary


@frappe.whitelist()
def day_details(crane, from_date, to_date, metric):
	start, end = report_period(dict(from_date=from_date, to_date=to_date))
	frappe.get_doc("Crane", crane).check_permission("read")
	for source in ("Rental Contract", "Crane Timesheet", "Crane Maintenance"):
		frappe.has_permission(source, "read", throw=True)
	today = getdate()
	documents = defaultdict(set)
	worked, recorded = submitted_days([crane], start, min(today, end), documents)
	booked, repaired = set(), set()

	def add_window(target, first, last, doctype, name):
		day = max(first, start)
		while day <= min(last, end):
			target.add(day)
			documents[day].add((doctype, name))
			day += DAY

	for row in bookings_by_crane(crane, start)[crane]:
		add_window(booked, row.start_date, row.expected_end_date, "Rental Contract", row.parent)
	for row in repairs_in_period([crane], start, min(today, end)):
		add_window(
			repaired,
			getdate(row.actual_start_date),
			min(today, repair_end(row, today)),
			"Crane Maintenance",
			row.name,
		)
	elapsed = {day for day in booked if day < today}
	days = {
		"booked_days": booked,
		"worked_days": worked[crane],
		"elapsed_days": elapsed,
		"elapsed_worked": elapsed & worked[crane],
		"downtime_days": recorded[crane] - worked[crane],
		"missing_days": elapsed - recorded[crane],
		"maintenance_days": repaired,
		"utilization": elapsed,
	}
	return [
		dict(day=day, documents=sorted(documents[day]), worked=day in worked[crane])
		for day in sorted(days[metric])
	]
