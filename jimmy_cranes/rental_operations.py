"""Permission-checked and audited crane booking actions."""

import frappe
from frappe import _
from frappe.utils import escape_html, now_datetime

from jimmy_cranes.rental_validation import RENTAL_ACTION, action_date, crane_display_name, project_doc


@frappe.whitelist()
def project_action(project, action, reason=None):
	if action not in ("Complete", "Cancel", "Reopen"):
		frappe.throw(_("Unknown Crane Project action."))
	doc = project_doc(project, "write", lock=True)
	if action == "Reopen":
		if doc.status not in ("Completed", "Cancelled"):
			frappe.throw(_("Only a Completed or Cancelled Crane Project can be reopened."))
		if not (reason or "").strip():
			frappe.throw(_("A reason is required to reopen a Crane Project."))
	elif doc.status != "Open":
		frappe.throw(_("Only an Open Crane Project can be closed."))
	if action == "Cancel" and not (reason or "").strip():
		frappe.throw(_("A reason is required to cancel a Crane Project."))
	old_status = doc.status
	doc.status = {"Complete": "Completed", "Cancel": "Cancelled", "Reopen": "Open"}[action]
	if action == "Complete":
		doc.completion_date = action_date(None)
	elif action == "Reopen":
		doc.completion_date = None
	doc.flags.rental_action = RENTAL_ACTION
	frappe.db.savepoint("crane_project_action")
	try:
		doc.save()
		doc.add_comment(
			"Info",
			_("Project status changed from {0} to {1} by {2}. Reason: {3}").format(
				escape_html(old_status), escape_html(doc.status), escape_html(frappe.session.user),
				escape_html((reason or "").strip() or "—"),
			),
		)
	except frappe.QueryDeadlockError:
		raise
	except Exception:
		frappe.db.rollback(save_point="crane_project_action")
		raise
	return doc.as_dict()


@frappe.whitelist()
def crane_action(assignment, project, row_names, action, date=None, reason=None):
	project_doc(project, "write", lock=True)
	doc = frappe.get_doc("Crane Assignment", assignment, for_update=True)
	doc.check_permission("write")
	if doc.project != project:
		frappe.throw(_("The assignment does not belong to the supplied Project."))
	names = frappe.parse_json(row_names) if isinstance(row_names, str) else row_names
	if (
		not isinstance(names, list)
		or not names
		or any(not isinstance(name, str) for name in names)
		or len(names) != len(set(names))
	):
		frappe.throw(_("Select one or more distinct crane rows."))
	rows = {row.name: row for row in doc.assigned_cranes}
	if set(names) - rows.keys():
		frappe.throw(_("Selected crane rows must belong to this assignment."))
	eligible = {
		"Reserve": ("Draft",),
		"Cancel": ("Draft", "Reserved"),
		"Undo Reserve": ("Reserved",),
		"Undo Cancel": ("Cancelled",),
	}
	if action not in eligible:
		frappe.throw(_("Unknown crane action."))
	if any(rows[name].status not in eligible[action] for name in names):
		frappe.throw(_("Select only {0} rows for {1}.").format(" / ".join(eligible[action]), action))
	effective = action_date(date) if action == "Cancel" else None
	if action in ("Cancel", "Undo Reserve", "Undo Cancel") and not (reason or "").strip():
		frappe.throw(_("A reason is required for cancellation or correction."))
	if action == "Undo Cancel":
		for name in names:
			if rows[name].status_before_cancel not in ("Draft", "Reserved"):
				frappe.throw(_("Row {0} has no previous status to restore.").format(rows[name].idx))
	audit = []
	for name in names:
		row = rows[name]
		old_status = row.status
		old_cancellation = row.cancellation_date
		row.status = {
			"Reserve": "Reserved",
			"Cancel": "Cancelled",
			"Undo Reserve": "Draft",
			"Undo Cancel": row.status_before_cancel,
		}[action]
		if action == "Cancel":
			row.status_before_cancel = old_status
			row.cancellation_date, row.cancellation_reason = effective, reason
		elif action == "Undo Cancel":
			row.status_before_cancel = None
			row.cancellation_date = None
			row.cancellation_reason = None
		row.last_action_by, row.last_action_at = frappe.session.user, now_datetime()
		audit.append((
			row.idx, row.crane, old_status, row.status,
			old_cancellation, row.cancellation_date,
		))
	doc.flags.rental_action = RENTAL_ACTION
	frappe.db.savepoint("crane_bulk_action")
	try:
		doc.save()
		for idx, crane, old_status, new_status, old_cancellation, new_cancellation in audit:
			doc.add_comment(
				"Info",
				_("Crane {0}, row {1}: {2} → {3} by {4}. Cancellation date: {5} → {6}. Reason: {7}").format(
					crane_display_name(crane), idx, escape_html(old_status), escape_html(new_status),
					escape_html(frappe.session.user), escape_html(str(old_cancellation or "—")),
					escape_html(str(new_cancellation or "—")), escape_html((reason or "").strip() or "—"),
				),
			)
	except frappe.QueryDeadlockError:
		# MariaDB already rolled back the transaction, including its savepoints.
		raise
	except Exception:
		frappe.db.rollback(save_point="crane_bulk_action")
		raise
	return doc.as_dict()
