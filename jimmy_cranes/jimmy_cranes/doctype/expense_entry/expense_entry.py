import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from jimmy_cranes.rental_queries import visible_allocations


class ExpenseEntry(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Expense amount must be greater than zero."))
		if self.crane and not visible_allocations(project=self.project, crane=self.crane):
			frappe.throw(_("Select a crane assigned to this Crane Project."))
		if self.employee and not frappe.db.exists("Crane Driver", {"employee": self.employee}):
			frappe.throw(_("Select an Employee linked to a Crane Driver."))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def project_crane_query(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	if not filters.get("project"):
		return []
	names = {row.crane for row in visible_allocations(project=filters["project"])}
	if not names:
		return []
	return frappe.get_list(
		"Crane",
		filters={"name": ["in", list(names)]},
		or_filters={"name": ["like", f"%{txt}%"], "crane_name": ["like", f"%{txt}%"]},
		fields=["name", "crane_name"],
		start=start,
		page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def driver_employee_query(doctype, txt, searchfield, start, page_len, filters):
	if not frappe.has_permission("Employee", "select"):
		frappe.throw(_("You cannot select Employees."), frappe.PermissionError)
	drivers = frappe.get_list(
		"Crane Driver",
		filters={"employee": ["is", "set"]},
		or_filters={"operator_name": ["like", f"%{txt}%"], "employee": ["like", f"%{txt}%"]},
		fields=["employee", "operator_name"],
		start=start,
		page_length=page_len,
	)
	return [(driver.employee, driver.operator_name) for driver in drivers]
