import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class CraneMaintenance(Document):
	def validate(self):
		before = self.get_doc_before_save()
		if before and before.expense_entry != self.expense_entry:
			frappe.throw(_("Use Create Expense to link an Expense Entry."))
		if before and before.status in ("Completed", "Cancelled") and self.status != before.status:
			frappe.throw(_("Completed or Cancelled maintenance cannot be reopened."))
		allowed = {
			"Planned": ("Planned", "In Progress", "Completed", "Cancelled"),
			"In Progress": ("In Progress", "Completed", "Cancelled"),
			"Completed": ("Completed",),
			"Cancelled": ("Cancelled",),
		}
		if self.status not in allowed.get(before.status if before else "Planned", ()):
			frappe.throw(_("Invalid maintenance status transition."))
		if before and before.crane != self.crane and before.status != "Planned":
			frappe.throw(_("A started maintenance record cannot move to another crane."))
		if before and before.expense_entry and any(
			self.get(field) != before.get(field)
			for field in ("crane", "project", "cost", "expense_type", "actual_end_date")
		):
			frappe.throw(_("Expense details cannot change after expense creation."))
		if flt(self.cost) < 0:
			frappe.throw(_("Maintenance cost cannot be negative."))
		if self.status == "Completed" and (flt(self.cost) <= 0 or not self.expense_type):
			frappe.throw(_("Set a positive cost and Expense Type before completing maintenance."))
		if self.planned_start_date and self.planned_end_date and getdate(self.planned_end_date) < getdate(self.planned_start_date):
			frappe.throw(_("Planned end date cannot precede the start date."))
		if self.status in ("In Progress", "Completed") and not self.actual_start_date:
			self.actual_start_date = today()
		if self.status == "Completed" and not self.actual_end_date:
			self.actual_end_date = today()
		if self.actual_end_date and not self.actual_start_date:
			frappe.throw(_("Set the actual start date before the end date."))
		if self.actual_start_date and self.actual_end_date and getdate(self.actual_end_date) < getdate(self.actual_start_date):
			frappe.throw(_("Actual end date cannot precede the start date."))
		if before and before.crane != self.crane:
			frappe.db.sql("SELECT name FROM `tabCrane` WHERE name IN %s ORDER BY name FOR UPDATE", (tuple(sorted((before.crane, self.crane))),))
		else:
			frappe.db.sql("SELECT name FROM `tabCrane` WHERE name=%s FOR UPDATE", self.crane)

	def after_insert(self):
		self.sync_crane_condition()

	def on_update(self):
		self.sync_crane_condition()
		before = self.get_doc_before_save()
		if self.status == "Completed" and (not before or before.status != "Completed"):
			self.make_expense()

	def sync_crane_condition(self):
		# The crane row was locked in validate, serializing concurrent records for this crane.
		condition, managed = frappe.db.get_value(
			"Crane", self.crane, ("operational_condition", "maintenance_condition_managed")
		)
		active = frappe.db.count("Crane Maintenance", {"crane": self.crane, "status": "In Progress"})
		if active and condition == "Operational":
			frappe.db.set_value(
				"Crane", self.crane,
				{"operational_condition": "Maintenance", "maintenance_condition_managed": 1},
			)
		elif not active and managed:
			frappe.db.set_value(
				"Crane", self.crane,
				{"operational_condition": "Operational" if condition == "Maintenance" else condition,
				 "maintenance_condition_managed": 0},
			)

	def on_trash(self):
		if self.status != "Planned" or self.expense_entry:
			frappe.throw(_("Only planned maintenance without an expense can be deleted."))

	def make_expense(self):
		if self.expense_entry and frappe.db.exists("Expense Entry", self.expense_entry):
			if frappe.db.get_value("Expense Entry", self.expense_entry, "docstatus") != 2:
				frappe.throw(_("An active Expense Entry is already linked to this maintenance."))
		expense = frappe.get_doc({
			"doctype": "Expense Entry",
			"project": self.project,
			"crane": self.crane,
			"crane_maintenance": self.name,
			"expense_type": self.expense_type,
			"posting_date": self.actual_end_date,
			"amount": self.cost,
			"description": _("Crane Maintenance {0}: {1}").format(self.name, self.description),
			"receipt": self.attachment,
		}).insert()
		# Keep completion and expense submission in the same transaction.
		expense.submit()
		self.expense_entry = expense.name
		frappe.db.set_value("Crane Maintenance", self.name, "expense_entry", expense.name, update_modified=False)
		return expense.name


@frappe.whitelist()
def create_expense(maintenance):
	doc = frappe.get_doc("Crane Maintenance", maintenance, for_update=True)
	doc.check_permission("write")
	if doc.status != "Completed" or flt(doc.cost) <= 0 or not doc.expense_type:
		frappe.throw(_("Complete maintenance with a positive cost and Expense Type first."))
	return doc.make_expense()
