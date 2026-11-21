import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.payment import payment_account


class CraneMaintenance(Document):
	def _validate_links(self):
		# Native amendments copy generated links before normal validation runs.
		if self.is_new() and self.amended_from:
			source = frappe.get_doc(self.doctype, self.amended_from)
			source.check_permission("read")
			if source.docstatus == 2:
				from heavy_equipment_rental.maintenance_posting import LINK_FIELDS
				for field in LINK_FIELDS + ("expense_entry", "grouped_expense", "legacy_lifecycle"):
					if self.get(field) and self.get(field) != source.get(field):
						frappe.throw(_("An amendment cannot supply unrelated generated document links."))
					self.set(field, None)
				self.status = "Planned"
		super()._validate_links()

	def _submit(self):
		return self._atomic_lifecycle(super()._submit)

	def _cancel(self):
		return self._atomic_lifecycle(super()._cancel)

	def _atomic_lifecycle(self, action):
		savepoint = "maintenance_" + frappe.generate_hash(length=10)
		frappe.db.savepoint(savepoint)
		try:
			return action()
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			raise

	def before_validate(self):
		if self._action == "submit":
			self.status = "Completed"
			self.actual_start_date = self.actual_start_date or today()
			self.actual_end_date = self.actual_end_date or today()
		elif self.docstatus == 0 and self.status in ("Completed", "Cancelled"):
			frappe.throw(_("Use Submit to complete Maintenance, or Cancel on a submitted Maintenance."))

	def before_submit(self):
		if self.repair_source not in (None, "", "Manual Documents"):
			from heavy_equipment_rental.maintenance_posting import validate_posting
			validate_posting(self)

	def on_submit(self):
		if self.repair_source not in (None, "", "Manual Documents"):
			from heavy_equipment_rental.maintenance_posting import post_documents
			previous = frappe.flags.maintenance_posting
			frappe.flags.maintenance_posting = self.name
			try:
				post_documents(self)
			finally:
				frappe.flags.maintenance_posting = previous
		elif self.cost_treatment == "Cash Expense":
			self.make_expense()
		from heavy_equipment_rental.crane_repairs import validate_maintenance
		validate_maintenance(self, require_postings=True)
		self.sync_crane_condition()

	def before_cancel(self):
		from heavy_equipment_rental.maintenance_cancellation import build_plan
		self._maintenance_cancel_plan = build_plan(self.name)
		for row in self._maintenance_cancel_plan:
			frappe.get_doc(row["doctype"], row["name"]).check_permission("cancel")
		self.status = "Cancelled"

	def on_cancel(self):
		for row in self._maintenance_cancel_plan:
			doc = frappe.get_doc(row["doctype"], row["name"])
			if doc.doctype != self.doctype and doc.docstatus == 1:
				doc.cancel()
		self.sync_crane_condition()

	def validate(self):
		before = self.get_doc_before_save()
		from heavy_equipment_rental.rental_validation import crane_company
		assignment = self.crane_assignment
		if self.crane_timesheet:
			assignment = frappe.db.get_value("Crane Timesheet", self.crane_timesheet, "assignment")
		company = (frappe.db.get_value("Rental Contract", assignment, "company") if assignment else None) or crane_company(self.crane)
		if self.is_new() and company:
			self.company = company
		elif company and self.company != company:
			frappe.throw(_("Maintenance Company must match the selected rental work and Crane."))
		# Blank old API records retain their original cash-expense behavior.
		self.cost_treatment = self.cost_treatment or "Cash Expense"
		from heavy_equipment_rental.maintenance_posting import validate_inputs
		validate_inputs(self)
		from heavy_equipment_rental.crane_repairs import validate_maintenance
		validate_maintenance(self)
		if before and (before.grouped_expense != self.grouped_expense or before.expense_entry != self.expense_entry):
			frappe.throw(_("The generated expense link cannot be edited."))
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
		if before and before.grouped_expense and any(
			self.get(field) != before.get(field)
			for field in ("crane", "crane_assignment", "crane_timesheet", "cost", "expense_type", "mode_of_payment", "credit_account", "actual_start_date", "actual_end_date")
		):
			frappe.throw(_("Expense details cannot change after expense creation."))
		if flt(self.cost) < 0:
			frappe.throw(_("Maintenance cost cannot be negative."))
		legacy_completed = before and before.status == "Completed" and not before.mode_of_payment and before.credit_account
		if self.cost_treatment == "Cash Expense" and self.status == "Completed" and (
			flt(self.cost) <= 0 or not self.expense_type or not (self.mode_of_payment or legacy_completed)
		):
			frappe.throw(_("Set a positive cost, Expense Entry Type and Mode of Payment before completing maintenance."))
		if self.mode_of_payment and self.expense_type and not self.grouped_expense:
			debit_name = frappe.db.get_value("Expense Entry Type", self.expense_type, "account")
			company = frappe.db.get_value("Account", debit_name, "company") if debit_name else None
			if company:
				self.credit_account = payment_account(self.mode_of_payment, company)
		if self.status in ("In Progress", "Completed") and not self.actual_start_date:
			self.actual_start_date = today()
		if self.status == "Completed" and not self.actual_end_date:
			self.actual_end_date = today()
		if self.actual_end_date and not self.actual_start_date:
			frappe.throw(_("Set the actual start date before the end date."))
		if self.actual_start_date and self.actual_end_date and getdate(self.actual_end_date) < getdate(self.actual_start_date):
			frappe.throw(_("Actual end date cannot precede the start date."))
		from heavy_equipment_rental.rental_context import validate_context
		validate_context(self)

		if before and before.crane != self.crane:
			frappe.db.sql("SELECT name FROM `tabCrane` WHERE name IN %s ORDER BY name FOR UPDATE", (tuple(sorted((before.crane, self.crane))),))
		else:
			frappe.db.sql("SELECT name FROM `tabCrane` WHERE name=%s FOR UPDATE", self.crane)

	def after_insert(self):
		self.sync_crane_condition()

	def on_update(self):
		self.sync_crane_condition()

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
		if self.status != "Planned" or self.grouped_expense:
			frappe.throw(_("Only planned maintenance without an expense can be deleted."))

	def make_expense(self):
		if self.cost_treatment != "Cash Expense":
			frappe.throw(_("This repair uses native accounting documents; a second cash expense is not allowed."))
		if self.grouped_expense:
			frappe.throw(_("A Grouped Expense is already linked to this maintenance."))
		expense = frappe.get_doc({
			"doctype": "Grouped Expense",
			"company": self.company,
			"crane": self.crane,
			"crane_maintenance": self.name,
			"crane_assignment": self.crane_assignment,
			"crane_timesheet": self.crane_timesheet,
			"mode_of_payment": self.mode_of_payment,
			"cost_center": self.repair_cost_center,
			"items": [{"posting_date": self.actual_end_date, "expense_entry_type": self.expense_type,
				"amount": self.cost, "description": _("Crane Maintenance {0}: {1}").format(self.name, self.description)}],
		})
		expense.flags.from_maintenance = True
		expense.insert().submit()
		self.db_set("grouped_expense", expense.name, update_modified=False)
		return expense.name


@frappe.whitelist()
def create_expense(maintenance):
	frappe.get_doc("Crane Maintenance", maintenance).check_permission("write")
	frappe.throw(_("Submit Maintenance to create its expense. To correct a submitted repair, use Cancel and Amend."))
