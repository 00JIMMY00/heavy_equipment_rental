import frappe
from frappe import _
from frappe.model.document import Document


class CraneDriver(Document):
	def validate(self):
		if self.is_new() and self.employee:
			frappe.throw(_("The Employee link is created automatically when the Crane Driver is saved."))
		before = self.get_doc_before_save()
		if before and before.employee and self.employee != before.employee:
			frappe.throw(_("The linked Employee cannot be changed."))
		if self.employee and not frappe.db.exists("Employee", self.employee):
			frappe.throw(_("The linked Employee does not exist."))

	def after_insert(self):
		first, _, remainder = self.operator_name.strip().partition(" ")
		employee = frappe.get_doc({
			"doctype": "Employee",
			"first_name": first,
			"last_name": remainder,
			"company": self.company,
			"gender": self.gender,
			"date_of_birth": self.date_of_birth,
			"date_of_joining": self.date_of_joining,
			"cell_number": self.phone,
		}).insert(ignore_permissions=True)
		self.db_set("employee", employee.name, update_modified=False)

	def on_update(self):
		if not self.employee:
			return
		employee = frappe.get_doc("Employee", self.employee)
		first, _, remainder = self.operator_name.strip().partition(" ")
		employee.update({
			"first_name": first,
			"last_name": remainder,
			"cell_number": self.phone,
			"company": self.company or employee.company,
			"gender": self.gender or employee.gender,
			"date_of_birth": self.date_of_birth or employee.date_of_birth,
			"date_of_joining": self.date_of_joining or employee.date_of_joining,
		})
		employee.flags.ignore_mandatory = True  # Legacy records may still need HR details.
		employee.save(ignore_permissions=True)
