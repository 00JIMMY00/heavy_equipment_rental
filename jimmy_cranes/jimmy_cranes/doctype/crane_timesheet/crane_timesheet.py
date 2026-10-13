from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from jimmy_cranes.rental_validation import (
	allocation_window,
	allocations,
	billable_totals,
	check_date_order,
	check_non_negative,
	interval,
	lock_cranes,
	project_doc,
	protect_legacy,
	work_days,
)


class CraneTimesheet(Document):
	def validate(self):
		project = project_doc(self.project, "write", lock=True)
		lock_cranes([self.crane])
		if self.is_new() and self.amended_from:
			source = frappe.get_doc("Crane Timesheet", self.amended_from, for_update=True)
			source.check_permission("amend")
			if source.docstatus != 2:
				frappe.throw(_("Only a cancelled timesheet can be amended."))
			# Frappe's Amend copies even no_copy fields. Keep the immutable source
			# on the original (linked by amended_from), never on the new report.
			for field in ("legacy_snapshot", "legacy_source_status", "legacy_needs_review"):
				if self.get(field) and self.get(field) != source.get(field):
					frappe.throw(_("Amendment migration history does not match its source."))
				self.set(field, 0 if field == "legacy_needs_review" else None)
		protect_legacy(self, ("legacy_snapshot", "legacy_source_status", "legacy_needs_review"))
		check_date_order(self.period_start, self.period_end, _("Timesheet period"))
		before = self.get_doc_before_save()
		if before and before.legacy_source_status == "Approved" and self.docstatus < 2:
			frappe.only_for(("System Manager", "Projects Manager"))
		incomplete = any(
			r.start_time in (None, "") or r.end_time in (None, "") for r in self.timesheet_entries
		)
		if before and before.legacy_needs_review and incomplete and self.docstatus == 0:
			if self.project != before.project or self.crane != before.crane:
				frappe.throw(
					_("Enter all verified shift times before changing a legacy sheet's Project or crane.")
				)
			previous = {r.name: r for r in before.timesheet_entries}
			for row in self.timesheet_entries:
				check_non_negative(row.price_per_hour, _("Row {0} hourly price").format(row.idx))
				if row.name not in previous or getdate(row.work_date) != getdate(
					previous[row.name].work_date
				):
					frappe.throw(
						_("Enter all verified shift times before changing legacy work dates or adding rows.")
					)
			# Keep original hours in the immutable snapshot. No shift boundaries
			# or invoice totals can be reconstructed safely from old hour totals.
			self.total_operator_hours = self.total_crane_billable_hours = self.total_amount = 0
			return
		if not self.timesheet_entries and self.docstatus == 1:
			frappe.throw(_("Add at least one shift before submitting the timesheet."))
		windows = [
			allocation_window(r) for r in allocations([self.crane], self.project) if allocation_window(r)
		]
		intervals, operator_hours = [], 0
		for row in self.timesheet_entries:
			check_non_negative(row.price_per_hour, _("Row {0} hourly price").format(row.idx))
			start, end = interval(row)
			for day in work_days(start, end):
				label = _("Row {0}, crane {1}, Project {2}, date {3}").format(
					row.idx, self.crane, self.project, day
				)
				if day > getdate(today()):
					frappe.throw(_("{0}: future work cannot be recorded.").format(label))
				if not getdate(self.period_start) <= day <= getdate(self.period_end):
					frappe.throw(_("{0}: shift is outside the timesheet period.").format(label))
				if project.status == "Complete" and (
					not project.completion_date or day > getdate(project.completion_date)
				):
					frappe.throw(
						_(
							"{0}: work after Project completion is not allowed. A missing legacy completion date needs review."
						).format(label)
					)
				if not any(first <= day <= last for first, last in windows):
					frappe.throw(
						_(
							"{0}: no reserved, active or historical completed allocation covers this work."
						).format(label)
					)
			row.worked_hours = (end - start).total_seconds() / 3600
			row.line_amount = row.worked_hours * flt(row.price_per_hour)
			operator_hours += row.worked_hours
			intervals.append((start, end, flt(row.price_per_hour)))
		self.total_operator_hours = operator_hours
		self.total_crane_billable_hours, self.total_amount = billable_totals(intervals)
		if before and before.legacy_needs_review:
			if not self.timesheet_entries:
				frappe.throw(_("Enter the verified shifts before resolving legacy review."))
			self.legacy_needs_review = 0
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
						).format(self.crane, other.timesheet)
					)

	def before_submit(self):
		if self.legacy_needs_review:
			frappe.throw(
				_("Verify and enter the original shift times before submitting this legacy timesheet.")
			)

	def before_cancel(self):
		project_doc(self.project, "write", lock=True)
		lock_cranes([self.crane])

	def on_trash(self):
		project_doc(self.project, "write", lock=True)
		if self.legacy_snapshot:
			frappe.throw(_("Keep migrated timesheet history. Cancel it instead of deleting it."))
