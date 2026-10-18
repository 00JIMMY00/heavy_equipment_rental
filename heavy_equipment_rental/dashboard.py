"""Permission-aware summary for the crane operations workspace."""

from collections import Counter

import frappe
from frappe.utils import add_days, getdate, nowdate


@frappe.whitelist()
def get_crane_dashboard():
	for doctype in ("Crane", "Crane Project", "Crane Timesheet", "Crane Maintenance", "Crane Assignment"):
		if not frappe.has_permission(doctype, "read"):
			frappe.throw(frappe._("Not permitted to view crane dashboard"), frappe.PermissionError)

	today = getdate(nowdate())
	month_start = today.replace(day=1)
	cranes = frappe.get_list("Crane", fields=["name", "crane_name", "model", "capacity_tons", "operational_condition"], limit_page_length=0)
	projects = frappe.get_list("Crane Project", fields=["name", "project_name", "customer", "status", "expected_end_date"], limit_page_length=0)
	timesheets = frappe.get_list(
		"Crane Timesheet",
		filters={"docstatus": 1, "period_start": ["between", [str(month_start), str(today)]]},
		fields=["total_crane_billable_hours", "total_amount", "sales_invoice", "period_start", "period_end"],
		limit_page_length=0,
	)
	maintenance = frappe.get_list(
		"Crane Maintenance",
		filters={"status": ["in", ["Planned", "In Progress"]]},
		fields=["name", "crane", "maintenance_type", "status", "planned_start_date"],
		limit_page_length=0,
	)
	assignments = frappe.get_list("Crane Assignment", fields=["name"], limit_page_length=0)
	reservations = frappe.get_all(
		"Assigned Crane",
		filters={"parenttype": "Crane Assignment", "parent": ["in", [row.name for row in assignments]]},
		fields=["crane", "start_date", "expected_end_date", "status"],
		limit_page_length=0,
	) if assignments else []
	active_cranes = {row.crane for row in reservations if row.status == "Reserved" and getdate(row.start_date) <= today <= getdate(row.expected_end_date)}
	conditions = Counter(row.operational_condition for row in cranes)
	upcoming = sorted(
		(row for row in maintenance if row.planned_start_date and today <= getdate(row.planned_start_date) <= add_days(today, 14)),
		key=lambda row: row.planned_start_date,
	)
	return {
		"as_of": str(today),
		"fleet_total": len(cranes),
		"operational": conditions["Operational"],
		"maintenance": conditions["Maintenance"],
		"inactive": conditions["Inactive"],
		"reserved_today": len(active_cranes),
		"available_today": sum(row.operational_condition == "Operational" and row.name not in active_cranes for row in cranes),
		"open_projects": sum(row.status == "Open" for row in projects),
		"overdue_projects": sum(row.status == "Open" and row.expected_end_date and getdate(row.expected_end_date) < today for row in projects),
		"hours_this_month": sum(float(row.total_crane_billable_hours or 0) for row in timesheets if getdate(row.period_start) >= month_start),
		"unbilled_timesheets": sum(not row.sales_invoice for row in timesheets),
		"upcoming_maintenance": [dict(row) for row in upcoming[:5]],
		"upcoming_maintenance_count": len(upcoming),
		"fleet": [dict(row, reserved_today=row.name in active_cranes) for row in cranes[:8]],
	}
