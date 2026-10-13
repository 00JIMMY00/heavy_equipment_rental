"""Permission-checked workflow actions. All writes share one request transaction."""

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from jimmy_cranes.rental_validation import RENTAL_ACTION, action_date, project_doc


@frappe.whitelist()
def project_action(project, action, date=None):
	doc = project_doc(project, "write", lock=True)
	target = {"Reserve": "Reserved", "Start": "In Progress", "Complete": "Complete"}.get(action)
	if not target:
		frappe.throw(_("Unknown Project action."))
	if action == "Start" and getdate(doc.expected_start_date) > getdate(today()):
		frappe.throw(_("The Project cannot start before its planned start date."))
	doc.flags.rental_action = RENTAL_ACTION
	doc.status = target
	if action == "Complete":
		doc.completion_date = action_date(date)
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def crane_action(assignment, project, row_names, action, date=None, reason=None):
	project_doc(project, "write", lock=True)
	frappe.db.sql("SELECT name FROM `tabCrane Assignment` WHERE name=%s FOR UPDATE", assignment)
	doc = frappe.get_doc("Crane Assignment", assignment, for_update=True)
	doc.check_permission("write")
	if doc.project != project:
		frappe.throw(_("The assignment does not belong to the supplied Project."))
	names = frappe.parse_json(row_names) if isinstance(row_names, str) else row_names
	if (
		not isinstance(names, list)
		or not names
		or any(not isinstance(n, str) for n in names)
		or len(names) != len(set(names))
	):
		frappe.throw(_("Select one or more distinct crane rows."))
	rows = {row.name: row for row in doc.assigned_cranes}
	if set(names) - rows.keys():
		frappe.throw(_("Selected crane rows must belong to this assignment."))
	eligible = {
		"Reserve": ("Draft",),
		"Start": ("Draft", "Reserved"),
		"Complete": ("In Progress",),
		"Cancel": ("Draft", "Reserved", "In Progress"),
	}
	if action not in eligible:
		frappe.throw(_("Unknown crane action."))
	effective = action_date(date) if action != "Reserve" else None
	if action == "Cancel" and not (reason or "").strip():
		frappe.throw(_("A cancellation reason is required."))
	for name in names:
		row = rows[name]
		if row.status not in eligible[action]:
			frappe.throw(
				_("Row {0}, crane {1}: {2} is not valid from {3}.").format(
					row.idx, row.crane, action, row.status
				)
			)
		row.status = {
			"Reserve": "Reserved",
			"Start": "In Progress",
			"Complete": "Complete",
			"Cancel": "Cancelled",
		}[action]
		if action == "Start":
			row.actual_start_date = effective
		elif action == "Complete":
			row.actual_end_date = effective
			row.late_completion_reason = reason
		elif action == "Cancel":
			row.cancellation_date = effective
			row.cancellation_reason = reason
		row.last_action_by, row.last_action_at = frappe.session.user, now_datetime()
	doc.flags.rental_action = RENTAL_ACTION
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def review_legacy_dates(assignment, project, row_name, actual_start_date, actual_end_date=None, reason=None):
	"""Explicit correction of unknown legacy dates, never inferred by migration."""
	frappe.only_for(("System Manager", "Projects Manager"))
	project_doc(project, "write", lock=True)
	frappe.db.sql("SELECT name FROM `tabCrane Assignment` WHERE name=%s FOR UPDATE", assignment)
	doc = frappe.get_doc("Crane Assignment", assignment, for_update=True)
	doc.check_permission("write")
	row = next((r for r in doc.assigned_cranes if r.name == row_name), None)
	if doc.project != project or not row or not row.legacy_needs_review:
		frappe.throw(_("Choose a legacy row awaiting date review in this Project and assignment."))
	row.actual_start_date = action_date(actual_start_date)
	if row.status == "Complete":
		if not actual_end_date:
			frappe.throw(_("Enter the verified actual completion date."))
		row.actual_end_date = action_date(actual_end_date)
		row.late_completion_reason = reason
	row.legacy_needs_review = 0
	row.last_action_by, row.last_action_at = frappe.session.user, now_datetime()
	doc.flags.rental_action = doc.flags.review_legacy = RENTAL_ACTION
	doc.save()
	return doc.as_dict()


def start_scheduled_projects():
	# Explicit per-project opt-in; use exactly the manual transition validation.
	for name in frappe.get_all(
		"Crane Project",
		filters={
			"auto_start_on_date": 1,
			"status": ["in", ["Draft", "Reserved"]],
			"expected_start_date": ["<=", today()],
		},
		pluck="name",
	):
		frappe.db.savepoint("scheduled_crane_project")
		try:
			project_action(name, "Start")
		except Exception:
			frappe.db.rollback(save_point="scheduled_crane_project")
			frappe.log_error(title="Crane Project automatic start failed", message=frappe.get_traceback())


@frappe.whitelist()
def review_project_completion(project, date):
	frappe.only_for(("System Manager", "Projects Manager"))
	doc = project_doc(project, "write", lock=True)
	if not doc.legacy_erpnext_project or doc.status != "Complete" or doc.completion_date:
		frappe.throw(_("This Project does not have a missing legacy completion date."))
	doc.completion_date = action_date(date)
	doc.flags.review_legacy = RENTAL_ACTION
	doc.save()
	return doc.as_dict()
