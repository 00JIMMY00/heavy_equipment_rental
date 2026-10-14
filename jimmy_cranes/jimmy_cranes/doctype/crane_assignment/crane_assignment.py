import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from jimmy_cranes.rental_validation import (
	RENTAL_ACTION,
	ROW_STATUSES,
	action_date,
	allocation_window,
	allocations,
	check_date_order,
	check_non_negative,
	crane_display_name,
	derived_status,
	entry_days,
	lock_cranes,
	project_doc,
	protect_legacy,
	ranges_overlap,
	recorded_work,
)


class CraneAssignment(Document):
	def validate(self):
		project = project_doc(self.project, "write", lock=True)
		before = self.get_doc_before_save()
		protect_legacy(self, ("legacy_snapshot",))
		old = {r.name: r for r in before.assigned_cranes} if before else {}
		if (
			before
			and before.project != self.project
			and any(r.status != "Draft" for r in before.assigned_cranes)
		):
			frappe.throw(_("An assignment with rental history cannot move to another Project."))
		current = {r.name for r in self.assigned_cranes}
		cranes = {r.crane for r in self.assigned_cranes} | {r.crane for r in old.values()}
		lock_cranes(cranes)
		crane_details = (
			frappe.db.sql(
				"SELECT name, crane_name, operational_condition FROM `tabCrane` WHERE name IN %s FOR UPDATE",
				(tuple(cranes),),
				as_dict=True,
			)
			if cranes
			else []
		)
		conditions = {row.name: row.operational_condition for row in crane_details}
		names = {row.name: row.crane_name for row in crane_details}
		for previous in old.values():
			if previous.name not in current and previous.status != "Draft":
				frappe.throw(
					_(
						"Keep allocation history. Cancel or complete crane {0} instead of deleting its row."
					).format(crane_display_name(previous.crane, names))
				)
		others = allocations(cranes, exclude=self.name) if cranes else []
		work = recorded_work(before.project if before else self.project, cranes)
		changed = []
		for row in self.assigned_cranes:
			previous = old.get(row.name)
			label = _("Assignment {0}, row {1}, crane {2}").format(
				self.name, row.idx, crane_display_name(row.crane, names)
			)
			check_date_order(row.start_date, row.expected_end_date, label)
			check_non_negative(row.rental_rate, label + " rental rate")
			if row.status not in ROW_STATUSES:
				frappe.throw(_("{0}: invalid status.").format(label))
			if getdate(row.start_date) < getdate(project.expected_start_date) or getdate(
				row.expected_end_date
			) > getdate(project.expected_end_date):
				frappe.throw(_("{0}: planned dates must be within the Project dates.").format(label))
			guarded = (
				"status",
				"actual_start_date",
				"actual_end_date",
				"cancellation_date",
				"cancellation_reason",
				"late_completion_reason",
				"last_action_by",
				"last_action_at",
				"legacy_needs_review",
			)
			if self.flags.rental_action is not RENTAL_ACTION:
				if previous:
					if any(str(row.get(f) or "") != str(previous.get(f) or "") for f in guarded):
						frappe.throw(
							_("{0}: use the crane Actions to change lifecycle or actual dates.").format(label)
						)
				elif row.status != "Draft" or any(row.get(f) for f in guarded[1:]):
					frappe.throw(
						_("{0}: new rows must be Draft. Reserve or start them using Actions.").format(label)
					)
			altered = (
				not previous
				or before.project != self.project
				or any(
					str(row.get(f) or "") != str(previous.get(f) or "")
					for f in ("crane", "start_date", "expected_end_date", "actual_end_date", "status")
				)
			)
			if project.status == "Complete" and altered and self.flags.review_legacy is not RENTAL_ACTION:
				frappe.throw(_("A Complete Project cannot receive new or changed allocations."))
			if (
				previous
				and previous.status in ("Complete", "Cancelled")
				and altered
				and self.flags.review_legacy is not RENTAL_ACTION
			):
				frappe.throw(_("{0}: terminal allocation history cannot be rewritten.").format(label))
			if previous and previous.crane != row.crane and previous.status != "Draft":
				frappe.throw(
					_(
						"{0}: a reserved or started crane cannot be replaced. Add a separate allocation."
					).format(label)
				)
			if row.status == "In Progress" and project.status != "In Progress":
				# Preserve explicitly flagged legacy records until reviewed.
				if altered:
					frappe.throw(_("{0}: start the Project before starting this crane.").format(label))
			if (
				altered
				and row.status in ("Reserved", "In Progress")
				and conditions.get(row.crane) != "Operational"
			):
				frappe.throw(_("{0}: crane is in Maintenance or Inactive.").format(label))
			if row.actual_start_date:
				date = action_date(row.actual_start_date)
				if not getdate(row.start_date) <= date <= getdate(row.expected_end_date):
					frappe.throw(_("{0}: actual start must fall within the planned period.").format(label))
			if row.status == "Complete":
				if not row.actual_end_date:
					if not (previous and previous.legacy_needs_review and row.legacy_needs_review):
						frappe.throw(_("{0}: actual completion date is required.").format(label))
				else:
					date = action_date(row.actual_end_date)
					if date < getdate(row.actual_start_date or row.start_date):
						frappe.throw(_("{0}: completion cannot precede the start.").format(label))
					if (
						date > getdate(row.expected_end_date)
						and not (row.late_completion_reason or "").strip()
					):
						frappe.throw(_("{0}: late completion requires a reason.").format(label))
					if date > getdate(project.expected_end_date):
						frappe.throw(
							_("{0}: extend the Project before recording late completion.").format(label)
						)
			elif row.actual_end_date:
				frappe.throw(_("{0}: only a Complete row has an actual completion date.").format(label))
			if row.status == "Cancelled":
				if not row.cancellation_date or not (row.cancellation_reason or "").strip():
					frappe.throw(_("{0}: cancellation date and reason are required.").format(label))
				action_date(row.cancellation_date)
				if previous and previous.status != "Cancelled":
					window = allocation_window(previous) or (
						getdate(previous.start_date),
						getdate(previous.expected_end_date),
					)
					if any(
						w.header_crane == previous.crane
						and any(window[0] <= d <= window[1] for d in entry_days(w))
						for w in work
					):
						frappe.throw(
							_(
								"{0}: recorded work exists. Complete/release this crane instead of cancelling its participation."
							).format(label)
						)
			if altered:
				changed.append(row)
		# Include all same-batch rows, not just other Projects. Inclusive dates
		# prevent two allocations sharing a handover day.
		for row in changed:
			window = allocation_window(row)
			if not window:
				continue
			for other in others + list(self.assigned_cranes):
				if other.name == row.name and other.get("parent") == row.parent:
					continue
				other_window = allocation_window(other)
				if row.crane == other.crane and other_window and ranges_overlap(*window, *other_window):
					frappe.throw(
						_("Crane {0}, {1} to {2}, overlaps assignment {3}, Project {4} ({5} to {6}).").format(
							crane_display_name(row.crane, names),
							*window,
							other.get("assignment") or self.name,
							other.get("project") or self.project,
							*other_window,
						)
					)
		# All recorded work, including drafts, must remain covered. This also
		# protects submitted history from date edits/imports and early release.
		if before and (changed or len(old) != len(self.assigned_cranes)):
			coverage = [r for r in others if r.project == before.project]
			if self.project == before.project:
				coverage += list(self.assigned_cranes)
			for work_row in work:
				for date in entry_days(work_row):
					was_covered = any(
						r.crane == work_row.header_crane
						and allocation_window(r)
						and allocation_window(r)[0] <= date <= allocation_window(r)[1]
						for r in old.values()
					)
					if was_covered and not any(
						r.crane == work_row.header_crane
						and allocation_window(r)
						and allocation_window(r)[0] <= date <= allocation_window(r)[1]
						for r in coverage
					):
						frappe.throw(
							_(
								"Crane {0}: change would invalidate timesheet {1} on {2}. Correct/cancel that timesheet first."
							).format(crane_display_name(work_row.header_crane, names), work_row.timesheet, date)
						)
		self.status = derived_status(self.assigned_cranes)
		self.project_start_date = project.expected_start_date
		self.project_end_date = project.expected_end_date
		self.completed_cranes = sum(row.status == "Complete" for row in self.assigned_cranes)
		self.total_cranes = sum(row.status != "Cancelled" for row in self.assigned_cranes)
		self.completion_percentage = (
			100 * self.completed_cranes / self.total_cranes if self.total_cranes else 0
		)

	def on_trash(self):
		project_doc(self.project, "write", lock=True)
		if any(row.status != "Draft" for row in self.assigned_cranes):
			frappe.throw(
				_(
					"Assignments with reservation or participation history cannot be deleted. Use Complete or Cancel Cranes."
				)
			)
