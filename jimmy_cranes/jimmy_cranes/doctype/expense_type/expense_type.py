import frappe
from frappe import _
from frappe.model.document import Document


class ExpenseType(Document):
	def before_import(self):
		if self.name != "EXT-MAINTENANCE":
			return
		existing = frappe.db.get_value("Expense Type", {"expense_type_name": "Maintenance"}, "name")
		if existing and existing != self.name and not frappe.db.exists("Expense Type", self.name):
			frappe.rename_doc("Expense Type", existing, self.name, force=True, show_alert=False)
		if not self.account and frappe.db.exists("Expense Type", self.name):
			self.account = frappe.db.get_value("Expense Type", self.name, "account")

	def validate(self):
		if not self.account:
			return
		account = frappe.db.get_value("Account", self.account, ("root_type", "is_group"), as_dict=True)
		if not account or account.root_type != "Expense" or account.is_group:
			frappe.throw(_("Choose a non-group Expense account."))
