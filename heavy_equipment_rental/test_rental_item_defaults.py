"""Draft demo invoices must not teach shared rental Items a demo account."""

import frappe
from erpnext import get_default_company
from frappe.tests.utils import FrappeTestCase

from heavy_equipment_rental.rental_items import default_service_item, preserve_rental_income_defaults


class TestRentalItemDefaults(FrappeTestCase):
	def setUp(self):
		item = frappe.get_doc("Item", default_service_item())
		if not any(row.company == get_default_company() for row in item.item_defaults):
			item.append("item_defaults", {"company": get_default_company()})
			item.save()

	def test_draft_invoice_account_stays_local_to_demo(self):
		company = frappe.get_doc("Company", get_default_company())
		item = default_service_item()
		row = frappe.db.get_value("Item Default", {"parent": item, "company": company.name}, "name")
		frappe.db.set_value("Item Default", row, "income_account", None)
		frappe.clear_document_cache("Item", item)
		account = frappe.get_doc(dict(doctype="Account", account_name="HER default isolation " + frappe.generate_hash(length=8),
			company=company.name, parent_account=frappe.db.get_value("Account", company.default_income_account, "parent_account"),
			account_type="Income Account")).insert()
		with preserve_rental_income_defaults():
			invoice = frappe.get_doc(dict(doctype="Sales Invoice", company=company.name,
				customer=frappe.db.get_value("Customer", {}, "name"),
				items=[dict(item_code=item, qty=1, rate=100, income_account=account.name,
					cost_center=company.cost_center)])).insert()
			self.assertEqual(frappe.db.get_value("Item Default", row, "income_account"), account.name)
		self.assertFalse(frappe.db.get_value("Item Default", row, "income_account"))
		self.assertEqual(invoice.items[0].income_account, account.name)
		regular = frappe.get_doc(dict(doctype="Sales Invoice", company=company.name,
			customer=invoice.customer, items=[dict(item_code=item, qty=1, rate=100)])).insert()
		self.assertEqual(regular.items[0].income_account, company.default_income_account)

	def test_existing_default_is_preserved_on_failure(self):
		item = default_service_item()
		row = frappe.db.get_value("Item Default", {"parent": item, "company": get_default_company()}, "name")
		before = frappe.db.get_value("Item Default", row, "income_account")
		with self.assertRaisesRegex(ValueError, "demo failed"):
			with preserve_rental_income_defaults():
				frappe.db.set_value("Item Default", row, "income_account", None)
				raise ValueError("demo failed")
		self.assertEqual(frappe.db.get_value("Item Default", row, "income_account"), before)
