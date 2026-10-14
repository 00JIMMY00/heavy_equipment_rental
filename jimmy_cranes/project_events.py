"""Crane-specific guards around the native ERPNext Project lifecycle."""

import frappe
from frappe import _
from frappe.utils import escape_html

from jimmy_cranes.rental_validation import allocations, crane_display_name


def before_validate(doc, method=None):
	if doc.is_new():
		return
	frappe.db.sql("SELECT name FROM `tabProject` WHERE name=%s FOR UPDATE", doc.name)
	rows = allocations(project=doc.name)
	if rows:
		# Native task progress must not implicitly finish a rental commitment.
		doc.percent_complete_method = "Manual"
		if doc.status not in ("Open", "Completed", "Cancelled"):
			frappe.throw(_("Projects with crane allocations use Open, Completed or Cancelled."))


def validate(doc, method=None):
	if doc.is_new() or doc.status not in ("Completed", "Cancelled"):
		return
	rows = allocations(project=doc.name)
	if not rows:
		return
	pending = [r for r in rows if r.status not in ("Released", "Cancelled")]
	if pending:
		cranes = frappe.get_all(
			"Crane", filters={"name": ["in", list({r.crane for r in pending})]}, fields=["name", "crane_name"]
		)
		names = {r.name: r.crane_name for r in cranes}
		frappe.throw(
			_("Resolve these crane allocations before closing the Project:<br>{0}").format(
				"<br>".join(
					_("{0} — assignment {1}, row {2}: {3}").format(
						crane_display_name(r.crane, names), escape_html(r.assignment), r.idx, r.status
					)
					for r in pending
				)
			)
		)
	drafts = frappe.db.sql(
		"SELECT name FROM `tabCrane Timesheet` WHERE project=%s AND docstatus=0 ORDER BY name FOR UPDATE",
		doc.name,
		pluck=True,
	)
	if drafts:
		frappe.throw(
			_("Submit or remove these draft Crane Timesheets before closing the Project: {0}.").format(
				", ".join(escape_html(name) for name in drafts)
			)
		)


def on_update(doc, method=None):
	if doc.has_value_changed("expected_start_date") or doc.has_value_changed("expected_end_date"):
		frappe.db.sql(
			"""UPDATE `tabCrane Assignment` SET project_start_date=%s, project_end_date=%s
			WHERE project=%s""",
			(doc.expected_start_date, doc.expected_end_date, doc.name),
		)
