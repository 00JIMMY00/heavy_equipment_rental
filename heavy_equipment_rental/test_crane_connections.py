"""Exercise native Connections counts and list targets against real child joins."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from heavy_equipment_rental.crane_connections import dashboard_data, get_connections


class TestCraneConnections(FrappeTestCase):
	def setUp(self):
		self.crane = frappe.get_doc(dict(doctype="Crane", crane_id=frappe.generate_hash(length=12), crane_name=frappe.generate_hash())).insert()

	def stub(self, doctype, **values):
		# Connections only read links; no accounting transactions need to be posted.
		doc = frappe.get_doc(dict(doctype=doctype, **values))
		doc.name = "connection-test-" + frappe.generate_hash(length=12)
		doc.db_insert()
		return doc

	def counts(self, *items):
		data = get_connections("Crane", self.crane.name, list(items))["count"]
		self.assertEqual(data["external_links_found"], [])
		return {row["doctype"]: row for row in data["internal_links_found"]}

	def test_child_assignments_and_invoice_header_and_rows_are_unioned(self):
		assignment = self.stub("Rental Contract")
		for _ in range(2):
			self.stub("Assigned Crane", parent=assignment.name, parenttype=assignment.doctype,
				parentfield="assigned_cranes", crane=self.crane.name)
		header = self.stub("Sales Invoice", crane=self.crane.name)
		child = self.stub("Sales Invoice")
		unrelated = self.stub("Sales Invoice")
		for parent in (header, child, child):
			self.stub("Sales Invoice Item", parent=parent.name, parenttype=parent.doctype,
				parentfield="items", crane=self.crane.name)
		rows = self.counts("Rental Contract", "Sales Invoice")
		self.assertEqual(rows["Rental Contract"]["names"], [assignment.name])
		self.assertEqual(rows["Sales Invoice"]["names"], sorted([header.name, child.name]))
		self.assertEqual(rows["Sales Invoice"]["count"], 2)
		self.assertNotIn(unrelated.name, rows["Sales Invoice"]["names"])

	def test_scalar_asset_link_empty_links_and_site_dimensions(self):
		asset = self.stub("Asset")
		self.crane.db_set("asset", asset.name)
		rows = self.counts("Asset", "Purchase Invoice", "Item")
		self.assertEqual(rows["Asset"]["names"], [asset.name])
		self.assertEqual(rows["Purchase Invoice"]["count"], 0)
		self.assertEqual(rows["Item"]["names"], [self.crane.item])
		data = dashboard_data()
		self.assertEqual(data["internal_links"]["Asset"], "asset")
		items = {dt for group in data["transactions"] for dt in group["items"]}
		self.assertTrue({"Sales Invoice", "Journal Entry", "Payment Entry", "Rental Contract"} <= items)

	def test_target_permissions_and_unrequested_doctypes(self):
		original = frappe.has_permission
		with patch("frappe.has_permission", side_effect=lambda dt, *a, **kw:
			False if dt == "Sales Invoice" else original(dt, *a, **kw)):
			self.assertEqual(self.counts("Sales Invoice"), {})
		self.assertEqual(self.counts("User"), {})
		with self.assertRaises(frappe.ValidationError):
			get_connections("Sales Invoice", self.crane.name)

	def test_source_permission_is_required(self):
		user = self.stub("User", email="connection-test@example.invalid", enabled=1, user_type="Website User")
		try:
			frappe.set_user(user.name)
			with self.assertRaises(frappe.PermissionError):
				get_connections("Crane", self.crane.name)
		finally:
			frappe.set_user("Administrator")

	def test_payments_follow_asset_and_invoice_references_without_duplicates(self):
		invoice = self.stub("Purchase Invoice")
		asset = self.stub("Asset", purchase_invoice=invoice.name)
		self.crane.db_set("asset", asset.name)
		sale = self.stub("Sales Invoice", crane=self.crane.name)
		payments = []
		for target in (invoice, sale):
			payment = self.stub("Payment Entry", crane=self.crane.name if target == sale else None)
			payments.append(payment.name)
			for _ in range(2):
				self.stub("Payment Entry Reference", parent=payment.name, parenttype="Payment Entry",
					parentfield="references", reference_doctype=target.doctype, reference_name=target.name)
		unrelated = self.stub("Payment Entry")
		self.stub("Payment Entry Reference", parent=unrelated.name, parenttype="Payment Entry",
			parentfield="references", reference_doctype="Sales Order", reference_name=invoice.name)
		self.assertEqual(self.counts("Payment Entry")["Payment Entry"]["names"], sorted(payments))
		original = frappe.has_permission
		with patch("frappe.has_permission", side_effect=lambda dt, *a, **kw:
			False if dt == "Purchase Invoice" else original(dt, *a, **kw)):
			self.assertEqual(self.counts("Payment Entry")["Payment Entry"]["names"], [payments[1]])

	def test_parts_payments_follow_only_unshared_company_cost_center(self):
		center = self.stub("Cost Center", company="cranes company", is_group=0)
		self.crane.db_set("sharing_cost_center", center.name)
		self.crane.db_set("sharing_company", "cranes company")
		invoice = self.stub("Purchase Invoice", company="cranes company")
		self.stub("Purchase Invoice Item", parent=invoice.name, parenttype="Purchase Invoice",
			parentfield="items", cost_center=center.name)
		payment = self.stub("Payment Entry")
		self.stub("Payment Entry Reference", parent=payment.name, parenttype="Payment Entry",
			parentfield="references", reference_doctype="Purchase Invoice", reference_name=invoice.name)
		self.assertEqual(self.counts("Payment Entry")["Payment Entry"]["names"], [payment.name])
		other = frappe.get_doc(dict(doctype="Crane", crane_id=frappe.generate_hash(length=12), crane_name=frappe.generate_hash())).insert()
		other.db_set("sharing_cost_center", center.name)
		self.assertEqual(self.counts("Payment Entry")["Payment Entry"]["names"], [])
		other.db_set("sharing_cost_center", None)
		invoice.db_set("company", "Other Company")
		self.assertEqual(self.counts("Payment Entry")["Payment Entry"]["names"], [])
