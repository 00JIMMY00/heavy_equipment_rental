"""Shared calendar-day and permission-filtered reads for the operations reports."""

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate

from heavy_equipment_rental.rental_queries import visible_allocations
from heavy_equipment_rental.rental_validation import allocation_window

DAY = timedelta(days=1)


def report_period(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Select From Date and To Date."))
	start, end = getdate(filters["from_date"]), getdate(filters["to_date"])
	if start > end:
		frappe.throw(_("From Date must be on or before To Date."))
	return start, end


def visible_fleet(crane=None):
	return frappe.get_list(
		"Crane",
		filters={"name": crane} if crane else {},
		fields=["name", "crane_name", "operational_condition"],
		order_by="name",
		limit_page_length=0,
	)


def bookings_by_crane(crane, since):
	bookings = defaultdict(list)
	for row in visible_allocations(crane=crane, ending_on_or_after=since):
		window = allocation_window(row)
		if window:
			row.start_date, row.expected_end_date = window
			bookings[row.crane].append(row)
	return bookings


def repairs_in_period(cranes, start, end=None):
	if not cranes:
		return []
	filters = {
		"crane": ["in", list(cranes)],
		"docstatus": ["<", 2],
		"actual_start_date": ["is", "set"],
		"status": ["in", ["In Progress", "Completed"]],
	}
	if end:
		filters["actual_start_date"] = ["<=", end]
	return frappe.get_list(
		"Crane Maintenance",
		filters=filters,
		or_filters=[
			["status", "=", "In Progress"],
			["actual_end_date", ">=", start],
			["actual_end_date", "is", "not set"],
		],
		fields=[
			"name",
			"crane",
			"status",
			"actual_start_date",
			"actual_end_date",
			"maintenance_type",
			"docstatus",
			"grouped_expense",
			"expense_entry",
			"cost_treatment",
			"cost",
			"company",
		],
		order_by="crane, actual_start_date desc, name",
		limit_page_length=0,
	)


def repair_end(job, as_of):
	# In Progress jobs can have a default Actual End Date even before completion.
	if job.status == "In Progress":
		return as_of
	return getdate(job.actual_end_date or job.actual_start_date)


def merged_windows(windows):
	merged = []
	for first, last in sorted(windows):
		if merged and (first - merged[-1][1]).days <= 1:
			merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
		else:
			merged.append((first, last))
	return merged


def days_in_period(windows, start, end):
	return sum(max(0, (min(last, end) - max(first, start)).days + 1) for first, last in windows)


def column(fieldname, label, fieldtype, width, options=None):
	return dict(fieldname=fieldname, label=_(label), fieldtype=fieldtype, width=width, options=options)
