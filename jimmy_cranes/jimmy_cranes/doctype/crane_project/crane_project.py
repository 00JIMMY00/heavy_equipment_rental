import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from jimmy_cranes.rental_validation import (
	RENTAL_ACTION,
	action_date,
	check_date_order,
	crane_display_name,
	protect_legacy,
)


class CraneProject(Document):
	def on_update(self):
		if self.has_value_changed("expected_start_date") or self.has_value_changed("expected_end_date"):
			frappe.db.sql(
				"""UPDATE `tabCrane Assignment`
				SET project_start_date=%s, project_end_date=%s
				WHERE project=%s""",
				(self.expected_start_date, self.expected_end_date, self.name),
			)

	def validate(self):
		check_date_order(self.expected_start_date, self.expected_end_date, _("Crane Project"))
		protect_legacy(self, ("legacy_erpnext_project", "legacy_snapshot"))
		before = self.get_doc_before_save()
		if not before:
			if self.status != "Draft" or self.completion_date:
				frappe.throw(_("New Crane Projects must start in Draft."))
			return
		frappe.db.sql("SELECT name FROM `tabCrane Project` WHERE name=%s FOR UPDATE", self.name)
		changed_completion = str(self.completion_date or "") != str(before.completion_date or "")
		if self.status != before.status:
			if self.flags.rental_action is not RENTAL_ACTION:
				frappe.throw(_("Use the Project Actions to change status."))
			allowed = {
				"Draft": ("Reserved", "In Progress"),
				"Reserved": ("In Progress",),
				"In Progress": ("Complete",),
				"Complete": (),
			}
			if self.status not in allowed.get(before.status, ()):
				frappe.throw(_("Invalid Project transition: {0} → {1}.").format(before.status, self.status))
			if self.status == "Complete":
				self.validate_completion()
		elif changed_completion:
			if (
				self.flags.review_legacy is not RENTAL_ACTION
				or not self.legacy_erpnext_project
				or before.completion_date
				or self.status != "Complete"
			):
				frappe.throw(_("Completion date is set by the Complete action."))
			self.validate_completion()
		if before.status == "Complete" and (
			getdate(self.expected_start_date) != getdate(before.expected_start_date)
			or getdate(self.expected_end_date) != getdate(before.expected_end_date)
		):
			frappe.throw(_("A Complete Project cannot be extended."))
		if self.has_value_changed("expected_start_date") or self.has_value_changed("expected_end_date"):
			outside = frappe.db.sql(
				"""SELECT a.parent, a.crane FROM `tabAssigned Crane` a JOIN `tabCrane Assignment` p ON p.name=a.parent
                WHERE p.project=%s AND a.status!='Cancelled' AND (a.start_date<%s OR COALESCE(a.actual_end_date,a.expected_end_date)>%s) LIMIT 1 FOR UPDATE""",
				(self.name, self.expected_start_date, self.expected_end_date),
			)
			if outside:
				frappe.throw(_("Project dates must cover crane {0} in assignment {1}.").format(
					crane_display_name(outside[0][1]), outside[0][0]
				))

	def validate_completion(self):
		from jimmy_cranes.rental_validation import allocations, entry_days, recorded_work

		self.completion_date = action_date(self.completion_date)
		if getdate(self.completion_date) < getdate(self.expected_start_date):
			frappe.throw(_("Completion date cannot precede the Project start."))
		rows = allocations(project=self.name)
		pending = next((r for r in rows if r.status not in ("Complete", "Cancelled")), None)
		if pending:
			frappe.throw(
				_(
					"Complete or cancel every crane row before completing this Project. Crane {0} in assignment {1} is still pending."
				).format(crane_display_name(pending.crane), pending.assignment)
			)
		if any(r.status == "Complete" and not r.actual_end_date for r in rows):
			frappe.throw(_("Review the missing actual completion dates on legacy crane rows first."))
		if any(
			r.actual_end_date and getdate(r.actual_end_date) > getdate(self.completion_date) for r in rows
		):
			frappe.throw(_("Project completion cannot precede a crane release date."))
		cranes = frappe.db.sql(
			"SELECT crane FROM `tabCrane Timesheet` WHERE project=%s AND docstatus<2 FOR UPDATE",
			self.name,
			pluck=True,
		)
		if any(
			day > getdate(self.completion_date)
			for work in recorded_work(self.name, cranes)
			for day in entry_days(work)
		):
			frappe.throw(_("Timesheet work exists after the proposed completion date."))
