"""Independent crane rental project lifecycle."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, getdate

from jimmy_cranes.rental_validation import RENTAL_ACTION, allocations, check_date_order, crane_display_name


class CraneProject(Document):
	def validate(self):
		check_date_order(self.expected_start_date, self.expected_end_date, _("Crane Project"))
		before = self.get_doc_before_save()
		if before and (
			self.expected_start_date != before.expected_start_date
			or self.expected_end_date != before.expected_end_date
		):
			for row in allocations(project=self.name):
				if (
					getdate(row.start_date) < getdate(self.expected_start_date)
					or getdate(row.expected_end_date) > getdate(self.expected_end_date)
					or (row.actual_end_date and getdate(row.actual_end_date) > getdate(self.expected_end_date))
				):
					frappe.throw(_("Project dates must cover assignment {0}, row {1} ({2} to {3}).").format(
						row.assignment, row.idx, row.start_date, row.expected_end_date
					))
		if not before:
			if self.status != "Open":
				frappe.throw(_("New Crane Projects must be Open."))
			return
		if self.status != before.status:
			allowed = {
				"Open": ("Completed", "Cancelled"),
				"Completed": ("Open",),
				"Cancelled": ("Open",),
			}
			if self.flags.rental_action is not RENTAL_ACTION or self.status not in allowed.get(before.status, ()):
				frappe.throw(_("Use the Crane Project Actions to change its status."))
			if self.status in ("Completed", "Cancelled"):
				self.validate_closure()
		elif self.status not in ("Open", "Completed", "Cancelled"):
			frappe.throw(_("Invalid Crane Project status."))

	def validate_closure(self):
		pending = [row for row in allocations(project=self.name) if row.status not in ("Released", "Cancelled")]
		if pending:
			cranes = frappe.get_all("Crane", filters={"name": ["in", list({row.crane for row in pending})]}, fields=["name", "crane_name"])
			names = {row.name: row.crane_name for row in cranes}
			frappe.throw(_("Resolve these crane allocations before closing the Crane Project:<br>{0}").format("<br>".join(
				_('{0} — assignment {1}, row {2}: {3}').format(crane_display_name(row.crane, names), escape_html(row.assignment), row.idx, row.status)
				for row in pending
			)))
		drafts = frappe.db.sql("SELECT name FROM `tabCrane Timesheet` WHERE project=%s AND docstatus=0 ORDER BY name FOR UPDATE", self.name, pluck=True)
		if drafts:
			frappe.throw(_("Submit or remove these draft Crane Timesheets before closing the Crane Project: {0}.").format(", ".join(escape_html(name) for name in drafts)))

	def on_update(self):
		if self.has_value_changed("expected_start_date") or self.has_value_changed("expected_end_date"):
			frappe.db.sql("""UPDATE `tabCrane Assignment` SET project_start_date=%s, project_end_date=%s WHERE project=%s""", (self.expected_start_date, self.expected_end_date, self.name))
