"""Permission-checked booking actions. Each bulk operation saves one parent atomically."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from jimmy_cranes.rental_validation import RENTAL_ACTION, action_date, project_doc


@frappe.whitelist()
def project_action(project, action):
	if action not in ("Complete", "Cancel"):
		frappe.throw(_("Unknown Crane Project action."))
	doc = project_doc(project, "write", lock=True)
	if doc.status != "Open":
		frappe.throw(_("Only an Open Crane Project can be closed."))
	doc.status = {"Complete": "Completed", "Cancel": "Cancelled"}[action]
	if action == "Complete":
		doc.completion_date = action_date(None)
	doc.flags.rental_action = RENTAL_ACTION
	frappe.db.savepoint("crane_project_action")
	try:
		doc.save()
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
		or any(not isinstance(n, str) for n in names)
		or len(names) != len(set(names))
	):
		frappe.throw(_("Select one or more distinct crane rows."))
	rows = {row.name: row for row in doc.assigned_cranes}
	if set(names) - rows.keys():
		frappe.throw(_("Selected crane rows must belong to this assignment."))
	eligible = {"Reserve": ("Draft",), "Release": ("Reserved",), "Cancel": ("Draft", "Reserved")}
	if action not in eligible:
		frappe.throw(_("Unknown crane action."))
	if any(rows[name].status not in eligible[action] for name in names):
		frappe.throw(_("Select only {0} rows for {1}.").format(" / ".join(eligible[action]), action))
	effective = action_date(date) if action != "Reserve" else None
	if action == "Cancel" and not (reason or "").strip():
		frappe.throw(_("A cancellation reason is required."))
	for name in names:
		row = rows[name]
		row.status = {"Reserve": "Reserved", "Release": "Released", "Cancel": "Cancelled"}[action]
		if action == "Release":
			row.actual_end_date = effective
		elif action == "Cancel":
			row.cancellation_date, row.cancellation_reason = effective, reason
		row.last_action_by, row.last_action_at = frappe.session.user, now_datetime()
	doc.flags.rental_action = RENTAL_ACTION
	frappe.db.savepoint("crane_bulk_action")
	try:
		doc.save()
	except frappe.QueryDeadlockError:
		# MariaDB already rolled back the transaction, including its savepoints.
		raise
	except Exception:
		frappe.db.rollback(save_point="crane_bulk_action")
		raise
	return doc.as_dict()
