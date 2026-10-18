import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from heavy_equipment_rental.rental_queries import visible_allocations


class ExpenseEntry(Document):
	def validate(self):
		before = self.get_doc_before_save()
		if self.journal_entry and (not before or self.journal_entry != before.journal_entry):
			frappe.throw(_("The Journal Entry link is managed by Expense Entry submission."))
		if flt(self.amount) <= 0:
			frappe.throw(_("Expense amount must be greater than zero."))
		if not self.project and not self.crane:
			frappe.throw(_("Select a Crane Project or Crane for this expense."))
		if self.crane_maintenance:
			maintenance = frappe.get_doc("Crane Maintenance", self.crane_maintenance)
			if maintenance.expense_entry and maintenance.expense_entry != self.name:
				if frappe.db.exists("Expense Entry", maintenance.expense_entry) and frappe.db.get_value(
					"Expense Entry", maintenance.expense_entry, "docstatus"
				) != 2:
					frappe.throw(_("An active Expense Entry is already linked to this maintenance."))
			if (
				maintenance.status != "Completed"
				or self.crane != maintenance.crane
				or self.project != maintenance.project
				or flt(self.amount) != flt(maintenance.cost)
				or self.expense_type != maintenance.expense_type
				or self.credit_account != maintenance.credit_account
			):
				frappe.throw(_("Expense details must match the completed Crane Maintenance record."))
		elif self.project and self.crane and not visible_allocations(project=self.project, crane=self.crane):
			frappe.throw(_("Select a crane assigned to this Crane Project."))
		if self.employee and not frappe.db.exists("Crane Driver", {"employee": self.employee}):
			frappe.throw(_("Select an Employee linked to a Crane Driver."))

	def before_submit(self):
		self.accounting_accounts()

	def on_submit(self):
		if self.journal_entry:
			frappe.throw(_("This Expense Entry already has a Journal Entry."))
		debit, credit, company = self.accounting_accounts()
		import erpnext

		cost_center = erpnext.get_default_cost_center(company)
		journal = frappe.get_doc({
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"is_system_generated": 1,
			"company": company,
			"posting_date": self.posting_date,
			"user_remark": _("Expense Entry {0}: {1}").format(self.name, self.description or self.expense_type),
			"accounts": [
				{"account": debit.name, "debit_in_account_currency": self.amount, "cost_center": cost_center},
				{"account": credit.name, "credit_in_account_currency": self.amount},
			],
		})
		# Expense Entry submit permission authorizes its generated accounting document.
		journal.flags.ignore_permissions = True
		journal.insert()
		journal.submit()
		self.journal_entry = journal.name
		frappe.db.set_value("Expense Entry", self.name, "journal_entry", journal.name, update_modified=False)

	def on_cancel(self):
		if not self.journal_entry:
			return
		if not frappe.db.exists("Journal Entry", self.journal_entry):
			frappe.throw(_("Linked Journal Entry {0} is missing.").format(self.journal_entry))
		journal = frappe.get_doc("Journal Entry", self.journal_entry, for_update=True)
		if journal.docstatus == 1:
			journal.flags.ignore_permissions = True
			journal.cancel()
		elif journal.docstatus == 0:
			frappe.throw(_("Linked Journal Entry {0} is still a draft.").format(journal.name))

	def accounting_accounts(self):
		debit_name = frappe.db.get_value("Expense Type", self.expense_type, "account")
		if not debit_name:
			frappe.throw(_("Set an Expense Account on Expense Type {0} before submitting.").format(self.expense_type))
		if not self.credit_account:
			frappe.throw(_("Select a Credit Account before submitting."))
		if debit_name == self.credit_account:
			frappe.throw(_("Expense and Credit accounts must be different."))
		debit = frappe.db.get_value(
			"Account", debit_name, ("name", "company", "root_type", "is_group", "account_currency"), as_dict=True
		)
		credit = frappe.db.get_value(
			"Account", self.credit_account,
			("name", "company", "root_type", "is_group", "account_type", "account_currency"), as_dict=True,
		)
		if not debit or debit.is_group or debit.root_type != "Expense":
			frappe.throw(_("Expense Type must link to a non-group Expense account."))
		if not credit or credit.is_group or credit.root_type not in ("Asset", "Liability"):
			frappe.throw(_("Choose a non-group Asset or Liability Credit Account."))
		if credit.account_type in ("Receivable", "Payable"):
			frappe.throw(_("A Receivable or Payable Credit Account needs a party; choose another account."))
		if not debit.company or credit.company != debit.company:
			frappe.throw(_("Expense and Credit accounts must belong to the same Company."))
		project_company = frappe.db.get_value("Crane Project", self.project, "company") if self.project else None
		if project_company and project_company != debit.company:
			frappe.throw(_("The Crane Project Company must match the expense accounts."))
		currency = frappe.db.get_value("Company", debit.company, "default_currency")
		if debit.account_currency != currency or credit.account_currency != currency:
			frappe.throw(_("Expense and Credit accounts must use the Company currency."))
		return debit, credit, debit.company


def guard_journal_entry_cancel(doc, method=None):
	linked = frappe.db.get_value("Expense Entry", {"journal_entry": doc.name, "docstatus": 1}, "name")
	if linked:
		frappe.throw(_("Cancel Expense Entry {0} to reverse this Journal Entry.").format(linked))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def project_crane_query(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	if not filters.get("project"):
		return frappe.get_list(
			"Crane",
			or_filters={"name": ["like", f"%{txt}%"], "crane_name": ["like", f"%{txt}%"]},
			fields=["name", "crane_name"],
			start=start,
			page_length=page_len,
			as_list=True,
		)
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
