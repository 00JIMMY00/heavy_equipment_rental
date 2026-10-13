"""Non-destructive upgrade from the original ERPNext-linked rental schema."""

from pathlib import Path

import frappe
from frappe.defaults import get_global_default, set_global_default

MIGRATION_KEY = "jimmy_cranes_independent_projects_v2"

from jimmy_cranes.rental_validation import derived_status


def raw_rows(doctype):
	return (
		frappe.db.sql(f"SELECT * FROM `tab{doctype}`", as_dict=True)
		if frappe.db.table_exists(doctype)
		else []
	)


def preflight():
	if get_global_default(MIGRATION_KEY):
		return
	if not frappe.db.table_exists("Crane Timesheet"):
		return
	sheets = raw_rows("Crane Timesheet")
	entries = raw_rows("Timesheet Entry")
	for sheet in sheets:
		if sheet.get("legacy_snapshot") or sheet.get("crane"):
			continue
		cranes = {r.get("crane") for r in entries if r.parent == sheet.name and r.get("crane")}
		if len(cranes) != 1 or sheet.docstatus == 1:
			frappe.throw(
				f"Timesheet {sheet.name} requires an approved migration: it has {len(cranes)} header crane candidates or is already submitted. No records were split or rewritten. Preserve/split its history before upgrading."
			)
	projects = {
		r.project
		for dt in ("Crane Assignment", "Crane Timesheet")
		for r in raw_rows(dt)
		if not r.get("legacy_snapshot")
	}
	for name in projects:
		if frappe.db.table_exists("Crane Project") and frappe.db.exists("Crane Project", name):
			continue
		doc = frappe.db.get_value(
			"Project", name, ["customer", "expected_start_date", "expected_end_date"], as_dict=True
		)
		if not doc or not all(doc.values()):
			frappe.throw(
				f"ERPNext Project {name} needs a customer and planned dates before its rental records can be migrated safely."
			)
	# Supplement the site database backup with a private, readable source snapshot.
	path = Path(frappe.get_site_path("private", "files", "jimmy_rental_v2_source.json"))
	if not path.exists() and any(not s.get("crane") for s in sheets):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(
			frappe.as_json(
				{
					dt: raw_rows(dt)
					for dt in (
						"Project",
						"Crane",
						"Crane Assignment",
						"Assigned Crane",
						"Crane Timesheet",
						"Timesheet Entry",
					)
				},
				indent=2,
			)
		)
		path.chmod(0o600)


def migrate_existing():
	if get_global_default(MIGRATION_KEY):
		return
	if not frappe.db.table_exists("Crane Project"):
		return
	assignments, rows = raw_rows("Crane Assignment"), raw_rows("Assigned Crane")
	sheets, entries = raw_rows("Crane Timesheet"), raw_rows("Timesheet Entry")
	sources = {
		r.project
		for r in assignments + sheets
		if not r.get("legacy_snapshot") and not frappe.db.exists("Crane Project", r.project)
	}
	for name in sorted(sources):
		source = frappe.db.get_value("Project", name, "*", as_dict=True)
		if not source:
			frappe.throw(
				f"Missing source Project {name}; migration stopped without discarding its rental records."
			)
		old = source.get("crane_rental_status") or "Draft"
		status = {
			"Confirmed": "Reserved",
			"Completed": "Complete",
			"Closed": "Complete",
			"Cancelled": "Complete",
		}.get(old, old)
		if status not in ("Draft", "Reserved", "In Progress", "Complete"):
			frappe.throw(f"Project {name}: unmapped legacy status {old}.")
		doc = frappe.get_doc(
			{
				"doctype": "Crane Project",
				"name": name,
				"naming_series": "CP-.#####",
				"project_name": source.project_name,
				"customer": source.customer,
				"expected_start_date": source.expected_start_date,
				"expected_end_date": source.expected_end_date,
				"status": status,
				"legacy_erpnext_project": name,
				"legacy_snapshot": frappe.as_json(source),
				"owner": source.owner,
				"creation": source.creation,
				"modified": source.modified,
				"modified_by": source.modified_by,
			}
		)
		# Historical import deliberately avoids workflow actions and invented dates.
		doc.db_insert()
	for assignment in assignments:
		if assignment.get("legacy_snapshot"):
			continue
		children = [r for r in rows if r.parent == assignment.name]
		snapshot = frappe.as_json(dict(assignment, assigned_cranes=children))
		for row in children:
			status = {"Working": "In Progress", "Completed": "Complete"}.get(row.status, row.status)
			values = {
				"expected_end_date": row.get("expected_end_date") or row.get("end_date"),
				"status": status,
				"legacy_needs_review": int(
					status in ("In Progress", "Complete")
					and (
						not row.get("actual_start_date")
						or (status == "Complete" and not row.get("actual_end_date"))
					)
				),
			}
			if status == "Cancelled" and not row.get("cancellation_reason"):
				# This is explicitly a migration annotation, not an invented reason/date.
				values["cancellation_reason"] = "Legacy cancellation; original reason unavailable."
				values["legacy_needs_review"] = 1
			row.update(values)
			frappe.db.set_value("Assigned Crane", row.name, values, update_modified=False)
		frappe.db.set_value(
			"Crane Assignment",
			assignment.name,
			{"status": derived_status(children), "legacy_snapshot": snapshot},
			update_modified=False,
		)
	for sheet in sheets:
		if sheet.get("legacy_snapshot") or sheet.get("crane"):
			continue
		children = [r for r in entries if r.parent == sheet.name]
		cranes = {r.get("crane") for r in children if r.get("crane")}
		if len(cranes) != 1 or sheet.docstatus == 1:
			frappe.throw(
				f"Timesheet {sheet.name}: migration requires explicit split/submitted-history handling."
			)
		values = {
			"crane": next(iter(cranes)),
			"legacy_snapshot": frappe.as_json(dict(sheet, timesheet_entries=children)),
			"legacy_source_status": sheet.get("status"),
			"legacy_needs_review": 1,
		}
		if sheet.get("status") == "Cancelled":
			values["docstatus"] = 2
			for row in children:
				frappe.db.set_value("Timesheet Entry", row.name, "docstatus", 2, update_modified=False)
		frappe.db.set_value("Crane Timesheet", sheet.name, values, update_modified=False)
	for crane in raw_rows("Crane"):
		if not crane.get("legacy_status") and crane.get("status"):
			frappe.db.set_value(
				"Crane",
				crane.name,
				{
					"legacy_status": crane.status,
					"operational_condition": crane.status
					if crane.status in ("Maintenance", "Inactive")
					else "Operational",
				},
				update_modified=False,
			)
		present = set(
			frappe.get_all(
				"Crane Period Price", filters={"parent": crane.name, "parenttype": "Crane"}, pluck="period"
			)
		)
		for index, period in enumerate(("Day", "Month", "Year"), 1):
			if period not in present:
				frappe.get_doc(
					{
						"doctype": "Crane Period Price",
						"parent": crane.name,
						"parenttype": "Crane",
						"parentfield": "period_prices",
						"idx": index,
						"period": period,
						"price": 0,
					}
				).db_insert()
	# Retain native Project data; retire only the app's former visible custom field.
	for field in ("Project-crane_rental_status", "Project-crane_rental_section"):
		if frappe.db.exists("Custom Field", field):
			frappe.db.set_value("Custom Field", field, "hidden", 1)
	frappe.clear_cache(doctype="Project")
	frappe.db.add_index(
		"Assigned Crane", ["crane", "start_date", "expected_end_date"], "crane_allocation_dates"
	)
	frappe.db.add_index("Crane Timesheet", ["crane", "docstatus"], "crane_submission")

	set_global_default(MIGRATION_KEY, "1")
