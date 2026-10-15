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
	booking_conflict,
	check_date_order,
	check_non_negative,
	crane_display_name,
	entry_days,
	lock_cranes,
	project_doc,
	recorded_work,
)


class CraneAssignment(Document):
	def onload(self):
		project = project_doc(self.project)
		self.project_start_date = project.expected_start_date
		self.project_end_date = project.expected_end_date

	def validate(self):
		project = project_doc(self.project, "write", lock=True)
		before = self.get_doc_before_save()
		old = {row.name: row for row in before.assigned_cranes} if before else {}
		if before and before.project != self.project and any(r.status != "Draft" for r in old.values()):
			frappe.throw(_("An assignment with booking history cannot move to another Project."))
		if project.status != "Open":
			frappe.throw(_("Crane allocations can only be changed on an Open Project."))
		cranes = {r.crane for r in self.assigned_cranes} | {r.crane for r in old.values()}
		lock_cranes(cranes)
		details = (
			frappe.db.sql(
				"SELECT name, crane_name, operational_condition FROM `tabCrane` WHERE name IN %s FOR UPDATE",
				(tuple(sorted(cranes)),),
				as_dict=True,
			)
			if cranes
			else []
		)
		names = {r.name: r.crane_name for r in details}
		conditions = {r.name: r.operational_condition for r in details}
		current = {r.name for r in self.assigned_cranes}
		for previous in old.values():
			if previous.name not in current and previous.status != "Draft":
				frappe.throw(
					_(
						"Keep booking history for crane {0}. Cancel an unused booking instead of deleting it."
					).format(crane_display_name(previous.crane, names))
				)
		others = allocations(cranes, exclude=self.name) if cranes else []
		work = recorded_work(before.project if before else self.project, cranes)
		work_days = [(w, day) for w in work for day in entry_days(w)]
		changed = []
		guarded = (
			"status",
			"status_before_cancel",
			"cancellation_date",
			"cancellation_reason",
			"last_action_by",
			"last_action_at",
		)
		business_fields = ("crane", "start_date", "expected_end_date", "rental_rate", "rental_rate_unit", *guarded)
		for row in self.assigned_cranes:
			previous = old.get(row.name)
			label = _("Assignment {0}, row {1}, crane {2}").format(
				self.name, row.idx, crane_display_name(row.crane, names)
			)
			check_date_order(row.start_date, row.expected_end_date, label)
			if (
				getdate(row.start_date) < getdate(project.expected_start_date)
				or getdate(row.expected_end_date) > getdate(project.expected_end_date)
			):
				frappe.throw(_("{0}: assignment dates must be within the Project dates ({1} to {2}).").format(
					label, project.expected_start_date, project.expected_end_date
				))
			check_non_negative(row.rental_rate, label + " rental rate")
			if row.rental_rate_unit not in ("Hour", "Day", "Month"):
				frappe.throw(_("{0}: choose Hour, Day or Month for the rental rate.").format(label))
			if row.status not in ROW_STATUSES:
				frappe.throw(_("{0}: invalid booking status.").format(label))
			if not previous:
				if row.status != "Draft" or any(row.get(f) for f in guarded[1:]):
					frappe.throw(
						_("{0}: new rows must be Draft. Use Reserve Selected to commit them.").format(label)
					)
			elif self.flags.rental_action is not RENTAL_ACTION and any(
				str(row.get(f) or "") != str(previous.get(f) or "") for f in guarded
			):
				frappe.throw(_("{0}: use an Actions button to change booking state.").format(label))
			if previous and row.status != previous.status:
				allowed = {
					"Draft": ("Reserved", "Cancelled"),
					"Reserved": ("Draft", "Cancelled"),
					"Cancelled": (previous.status_before_cancel,) if previous.status_before_cancel else ("Draft", "Reserved"),
				}
				if row.status not in allowed.get(previous.status, ()):
					frappe.throw(
						_("{0}: invalid transition from {1} to {2}.").format(
							label, previous.status, row.status
						)
					)
			altered = (
				not previous
				or before.project != self.project
				or any(str(row.get(f) or "") != str(previous.get(f) or "") for f in business_fields)
			)
			if previous and previous.status == "Cancelled" and altered and (
				self.flags.rental_action is not RENTAL_ACTION or row.status == previous.status
			):
				frappe.throw(_("{0}: terminal booking history cannot be rewritten.").format(label))
			if previous and previous.status != "Draft" and previous.crane != row.crane:
				frappe.throw(
					_("{0}: a committed crane cannot be replaced. Add a separate allocation.").format(label)
				)
			if altered and row.status == "Reserved" and conditions.get(row.crane) != "Operational":
				frappe.throw(_("{0}: crane is in Maintenance or Inactive.").format(label))
			if row.status == "Cancelled":
				if row.status_before_cancel and row.status_before_cancel not in ("Draft", "Reserved"):
					frappe.throw(_("{0}: invalid status before cancellation.").format(label))
				if not row.cancellation_date or not (row.cancellation_reason or "").strip():
					frappe.throw(_("{0}: cancellation date and reason are required.").format(label))
				action_date(row.cancellation_date)
				if previous and previous.status != "Cancelled":
					start, end = getdate(previous.start_date), getdate(previous.expected_end_date)
					if any(w.header_crane == previous.crane and start <= day <= end for w, day in work_days):
						frappe.throw(
							_(
								"{0}: recorded work exists, including draft Timesheets. Keep the booking Reserved."
							).format(label)
						)
			elif row.status_before_cancel or row.cancellation_date or row.cancellation_reason:
				frappe.throw(_("{0}: cancellation details require Cancelled status.").format(label))
			if altered:
				changed.append(row)
		conflicts = []
		for row in changed:
			for other in others + list(self.assigned_cranes):
				if other.name == row.name and other.get("parent") == row.parent:
					continue
				if booking_conflict(row, other):
					conflicts.append(
						_(
							"Crane {0}: row {1} conflicts with assignment {2}, row {3}, Project {4} ({5} to {6})."
						).format(
							crane_display_name(row.crane, names),
							row.idx,
							other.get("assignment") or self.name,
							other.idx,
							other.get("project") or self.project,
							*allocation_window(other),
						)
					)
		if conflicts:
			frappe.throw("<br>".join(conflicts))
		if before and (changed or len(old) != len(self.assigned_cranes)):
			coverage = [r for r in others if r.project == before.project]
			if self.project == before.project:
				coverage += list(self.assigned_cranes)
			for work_row, day in work_days:

				def covers(row):
					window = allocation_window(row)
					return row.crane == work_row.header_crane and window and window[0] <= day <= window[1]

				if any(covers(r) for r in old.values()) and not any(covers(r) for r in coverage):
					frappe.throw(
						_(
							"Crane {0}: change would invalidate Timesheet {1} on {2}. Keep recorded work within the booking dates."
						).format(crane_display_name(work_row.header_crane, names), work_row.timesheet, day)
					)
		self.project_start_date = project.expected_start_date
		self.project_end_date = project.expected_end_date

	def on_trash(self):
		project_doc(self.project, "write", lock=True)
		if any(row.status != "Draft" for row in self.assigned_cranes):
			frappe.throw(
				_("Assignments with booking history cannot be deleted. Cancel unused bookings instead.")
			)
