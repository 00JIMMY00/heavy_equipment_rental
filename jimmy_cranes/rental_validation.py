"""Shared rental rules. Dates are inclusive; shift intervals are half-open."""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, get_time, getdate, today

RENTAL_ACTION = object()  # Cannot be supplied through JSON/import fields.

ROW_STATUSES = ("Draft", "Reserved", "Cancelled")


def check_date_order(start, end, label):
	if not start or not end or getdate(start) > getdate(end):
		frappe.throw(_("{0}: provide a start date on or before the end date.").format(label))


def check_non_negative(value, label):
	if flt(value) < 0:
		frappe.throw(_("{0} cannot be negative.").format(label))


def project_doc(name, permission="read", lock=False):
	if lock:
		frappe.db.sql("SELECT name FROM `tabCrane Project` WHERE name=%s FOR UPDATE", name)
	doc = frappe.get_doc("Crane Project", name, for_update=lock)
	doc.check_permission(permission)
	return doc


def lock_cranes(names):
	names = tuple(sorted(set(filter(None, names))))
	if names:
		frappe.db.sql("SELECT name FROM `tabCrane` WHERE name IN %s ORDER BY name FOR UPDATE", (names,))


def crane_display_name(code, names=None):
	"""Use the human-readable crane name in messages; retain codes as database keys."""
	name = (
		names.get(code) if names is not None else frappe.db.get_value("Crane", code, "crane_name")
	) or code
	return escape_html(str(name))


def action_date(value):
	date = getdate(value or today())
	if date > getdate(today()):
		frappe.throw(_("An actual action date cannot be in the future."))
	return date


def allocation_window(row):
	if row.status != "Reserved" or not row.start_date:
		return None
	return (getdate(row.start_date), getdate(row.expected_end_date)) if row.expected_end_date else None


def booking_conflict(row, other):
	window, other_window = allocation_window(row), allocation_window(other)
	if not window or not other_window or row.crane != other.crane:
		return False
	return ranges_overlap(*window, *other_window)


def ranges_overlap(start, end, other_start, other_end):
	return getdate(start) <= getdate(other_end) and getdate(other_start) <= getdate(end)


def allocations(cranes=None, project=None, exclude=None, lock=True):
	conditions = ["a.parenttype='Crane Assignment'"]
	args = {}
	if cranes:
		conditions.append("a.crane IN %(cranes)s")
		args["cranes"] = tuple(cranes)
	if project:
		conditions.append("p.project=%(project)s")
		args["project"] = project
	if exclude:
		conditions.append("p.name!=%(exclude)s")
		args["exclude"] = exclude
	return frappe.db.sql(
		"""SELECT a.*, p.project, p.name AS assignment
        FROM `tabAssigned Crane` a JOIN `tabCrane Assignment` p ON p.name=a.parent
        WHERE """
		+ " AND ".join(conditions)
		+ (" FOR UPDATE" if lock else ""),
		args,
		as_dict=True,
	)


def interval(row):
	if (
		not row.work_date
		or row.start_time is None
		or row.end_time is None
		or row.start_time == ""
		or row.end_time == ""
	):
		frappe.throw(_("Row {0}: work date, start time and end time are required.").format(row.idx))
	try:
		start = datetime.combine(getdate(row.work_date), get_time(row.start_time))
		end = datetime.combine(getdate(row.work_date), get_time(row.end_time)) + timedelta(
			days=cint(row.ends_next_day)
		)
	except (ValueError, TypeError):
		frappe.throw(_("Row {0}: invalid shift time.").format(row.idx))
	hours = (end - start).total_seconds() / 3600
	if not 0 < hours <= 24 or cint(row.ends_next_day) not in (0, 1):
		frappe.throw(
			_(
				"Row {0}: shift must be longer than zero and at most 24 hours. Mark Ends Next Day for overnight work."
			).format(row.idx)
		)
	return start, end


def work_days(start, end):
	"""Midnight end is exclusive: 20:00 to 00:00 works only the first day."""
	date, last = start.date(), (end - timedelta(microseconds=1)).date()
	while date <= last:
		yield date
		date += timedelta(days=1)


def billable_totals(intervals):
	"""Sweep interval boundaries; count each crane minute once, reject rate ambiguity."""
	events = defaultdict(list)
	for key, (start, end, rate) in enumerate(intervals):
		events[start].append((key, Decimal(str(rate))))
		events[end].append((key, None))
	active, previous, hours, amount = {}, None, Decimal(0), Decimal(0)
	for timestamp in sorted(events):
		if previous is not None and active:
			rates = set(active.values())
			if len(rates) > 1:
				frappe.throw(
					_(
						"Overlapping operator intervals have different hourly prices. Use the same agreed price for the overlapping time."
					)
				)
			duration = Decimal(str((timestamp - previous).total_seconds())) / Decimal(3600)
			hours += duration
			amount += duration * next(iter(rates))
		for key, rate in events[timestamp]:
			if rate is None:
				active.pop(key, None)
			else:
				active[key] = rate
		previous = timestamp
	return float(hours), float(amount)


def recorded_work(project, cranes):
	if not cranes:
		return []
	return frappe.db.sql(
		"""SELECT e.*, s.name AS timesheet, s.crane AS header_crane,
        s.docstatus AS sheet_docstatus
        FROM `tabTimesheet Entry` e JOIN `tabCrane Timesheet` s ON s.name=e.parent
        WHERE e.parenttype='Crane Timesheet' AND s.project=%s AND s.crane IN %s
        AND s.docstatus<2 FOR UPDATE""",
		(project, tuple(cranes)),
		as_dict=True,
	)


def entry_days(row):
	return list(work_days(*interval(row)))
