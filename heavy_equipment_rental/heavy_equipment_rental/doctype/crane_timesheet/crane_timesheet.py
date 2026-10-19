from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.rental_validation import (
	allocation_window,
	allocations,
	billable_totals,
	check_date_order,
	check_non_negative,
	crane_display_name,
	interval,
	lock_cranes,
	project_doc,
	work_days,
)


@frappe.whitelist()
def default_timesheet_entries(period_start, period_end):
	if not frappe.has_permission("Crane Timesheet", "create"):
		frappe.throw(_("You cannot create Crane Timesheets."), frappe.PermissionError)
	check_date_order(period_start, period_end, _("Timesheet period"))
	start, end = getdate(period_start), getdate(period_end)
	if (end - start).days > 366:
		frappe.throw(_("Choose a timesheet period of at most 367 days."))
	settings = frappe.get_single("Heavy Equipment Rental Settings")
	settings.check_permission("read")
	start_time = str(settings.day_shift_start_time or "08:00:00")
	end_time = str(settings.day_shift_end_time or "16:00:00")
	return [
		{
			"work_date": str(start + timedelta(days=offset)),
			"start_time": start_time,
			"end_time": end_time,
			"ends_next_day": 0,
		}
		for offset in range((end - start).days + 1)
	]


class CraneTimesheet(Document):
	def before_update_after_submit(self):
		before = self.get_doc_before_save()
		if before and self.sales_invoice != before.sales_invoice:
			frappe.throw(_("The Sales Invoice link is managed by Generate Sales Invoice."))

	def validate(self):
		project = project_doc(self.project, "write", lock=True)
		lock_cranes([self.crane])
		crane_name = crane_display_name(self.crane)
		check_date_order(self.period_start, self.period_end, _("Timesheet period"))
		if self.amended_from:
			source = frappe.get_doc("Crane Timesheet", self.amended_from, for_update=True)
			source.check_permission("amend")
			if source.docstatus != 2 or source.project != self.project or source.crane != self.crane:
				frappe.throw(_("Amend a cancelled Timesheet for this same Project and crane."))
		if project.status != "Open":
			frappe.only_for(("System Manager", "Projects Manager"))
			if not self.amended_from:
				frappe.throw(_("Closed Projects accept only authorized amendments of cancelled Timesheets."))
			# A correction cannot introduce work dates that were not in the original record.
			original_days = {day for row in source.timesheet_entries for day in work_days(*interval(row))}
			if any(
				day not in original_days
				for row in self.timesheet_entries
				for day in work_days(*interval(row))
			):
				frappe.throw(_("An amendment on a closed Project cannot add new work dates."))
		if not self.timesheet_entries and self.docstatus == 1:
			frappe.throw(_("Add at least one shift before submitting the timesheet."))
		bookings = [
			(r, allocation_window(r))
			for r in allocations([self.crane], self.project)
			if allocation_window(r)
		]
		crane_hour_price = None
		intervals, operator_hours = [], 0
		for row in self.timesheet_entries:
			check_non_negative(row.price_per_hour, _("Row {0} hourly price").format(row.idx))
			start, end = interval(row)
			days = list(work_days(start, end))
			for day in days:
				label = _("Row {0}, crane {1}, Project {2}, date {3}").format(
					row.idx, crane_name, self.project, day
				)
				if day > getdate(today()):
					frappe.throw(_("{0}: future work cannot be recorded.").format(label))
				if not getdate(self.period_start) <= day <= getdate(self.period_end):
					frappe.throw(_("{0}: shift is outside the timesheet period.").format(label))
				if not any(first <= day <= last for _, (first, last) in bookings):
					frappe.throw(_("{0}: no Reserved allocation covers this work.").format(label))
			if not flt(row.price_per_hour):
				matching = [booking for booking, (first, last) in bookings if all(first <= day <= last for day in days)]
				if len(matching) != 1:
					frappe.throw(_("Row {0}: a shift with no hourly price must fit one crane assignment. Split the shift at the assignment boundary.").format(row.idx))
				booking = matching[0]
				if booking.rental_rate_unit == "Hour" and flt(booking.rental_rate):
					row.price_per_hour = booking.rental_rate
				else:
					if crane_hour_price is None:
						crane_hour_price = frappe.db.get_value(
							"Crane Period Price", {"parent": self.crane, "parenttype": "Crane", "period": "Hour"}, "price"
						) or 0
					row.price_per_hour = crane_hour_price
			row.worked_hours = (end - start).total_seconds() / 3600
			row.line_amount = row.worked_hours * flt(row.price_per_hour)
			operator_hours += row.worked_hours
			intervals.append((start, end, flt(row.price_per_hour)))
		self.total_operator_hours = operator_hours
		self.total_crane_billable_hours, self.total_amount = billable_totals(intervals)
		if intervals:
			existing = frappe.db.sql(
				"""SELECT e.*, s.name AS timesheet FROM `tabTimesheet Entry` e
                JOIN `tabCrane Timesheet` s ON s.name=e.parent
                WHERE e.parenttype='Crane Timesheet' AND s.crane=%s AND s.docstatus=1 AND s.name!=%s
                AND e.work_date BETWEEN %s AND %s FOR UPDATE""",
				(
					self.crane,
					self.name or "",
					min(s.date() for s, e, r in intervals) - timedelta(days=1),
					max(e.date() for s, e, r in intervals),
				),
				as_dict=True,
			)
			for other in existing:
				other_start, other_end = interval(other)
				if any(start < other_end and other_start < end for start, end, rate in intervals):
					frappe.throw(
						_(
							"Crane {0}: shift overlaps submitted timesheet {1}. Cancel/amend that sheet before billing the same crane time again."
						).format(crane_name, other.timesheet)
					)

	def before_cancel(self):
		project_doc(self.project, "write", lock=True)
		lock_cranes([self.crane])
		invoice = frappe.db.get_value("Crane Timesheet", self.name, "sales_invoice")
		if invoice and frappe.db.exists("Sales Invoice", invoice):
			if frappe.db.get_value("Sales Invoice", invoice, "docstatus") != 2:
				frappe.throw(_("Cancel or remove Sales Invoice {0} before cancelling this Crane Timesheet.").format(invoice))

	def on_trash(self):
		project_doc(self.project, "write", lock=True)
