"""Native Asset links, live valuation, ownership dates and accounting boundaries."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from heavy_equipment_rental.crane_assets import asset_summary


class TestCrane(FrappeTestCase):
	def setUp(self):
		self.key = "HER asset " + frappe.generate_hash(length=8)
		self.company = frappe.get_doc("Company", "cranes company")
		accounts = {}
		for field, account_type, root in (("fixed_asset_account", "Fixed Asset", "Asset"),
			("accumulated_depreciation_account", "Accumulated Depreciation", "Asset"),
			("depreciation_expense_account", "Depreciation", "Expense")):
			account = frappe.db.get_value("Account", dict(company=self.company.name, account_type=account_type,
				is_group=0, disabled=0), "name")
			if not account:
				account = frappe.get_doc(dict(doctype="Account", account_name=self.key + " " + field,
					company=self.company.name, account_type=account_type,
					parent_account=frappe.db.get_value("Account", dict(company=self.company.name, root_type=root, is_group=1), "name"))).insert().name
			accounts[field] = account
		category = frappe.get_doc(dict(doctype="Asset Category", asset_category_name=self.key,
			enable_cwip_accounting=0, accounts=[dict(company_name=self.company.name, **accounts)])).insert()
		self.accounts = accounts
		item = frappe.get_doc(dict(doctype="Item", item_code=self.key, item_name=self.key,
			item_group=frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
			stock_uom="Nos", is_stock_item=0, is_fixed_asset=1, asset_category=category.name)).insert()
		location = frappe.get_doc(dict(doctype="Location", location_name=self.key)).insert()
		self.asset = frappe.get_doc(dict(doctype="Asset", asset_name=self.key, item_code=item.name,
			company=self.company.name, cost_center=self.company.cost_center, location=location.name,
			asset_owner="Company", asset_quantity=1, is_existing_asset=1, calculate_depreciation=0,
			purchase_date=today(), available_for_use_date=today(), gross_purchase_amount=100000,
			opening_accumulated_depreciation=20000)).insert()
		self.crane = frappe.get_doc(dict(doctype="Crane", crane_id=frappe.generate_hash(length=12), crane_name=self.key)).insert()

	def link(self):
		self.crane.asset = self.asset.name
		self.crane.save()

	def sharing(self):
		supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=self.key,
			supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
		self.crane.update(dict(settlement_revenue_basis="Invoice Grand Total", distribution_posting="Source Revenue Accounts", settlement_approval="On Invoice Submission", include_depreciation=0, ownership_type="Shared Ownership", sharing_company=self.company.name,
			agreement_effective_from=add_days(today(), -10)))
		self.crane.set("ownership_partners", [dict(is_company=1, ownership_percentage=25, profit_percentage=60),
			dict(supplier=supplier.name, ownership_percentage=75, profit_percentage=40)])
		self.crane.save()

	def test_link_uses_full_value_without_posting_or_changing_service_item(self):
		counts = {dt: frappe.db.count(dt) for dt in ("GL Entry", "Journal Entry", "Payment Entry")}
		service_item = self.crane.item
		self.link()
		data = asset_summary(self.crane.name)
		self.assertEqual((data["gross_purchase_amount"], data["book_value"]), (100000, 80000))
		self.assertEqual(data["company_ownership_percentage"], 100)
		self.assertEqual(data["recognition_basis"], "Company Owned")
		self.assertEqual(data["shares"], [])
		self.assertEqual(self.crane.item, service_item)
		self.assertNotEqual(service_item, self.asset.item_code)
		self.assertFalse(frappe.get_doc("Item", service_item).is_fixed_asset)
		self.assertFalse(frappe.copy_doc(self.crane, ignore_no_copy=False).asset)
		self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})

	def test_duplicate_asset_and_grouped_assets_rejected(self):
		self.link()
		with self.assertRaisesRegex(frappe.ValidationError, "already linked"):
			frappe.get_doc(dict(doctype="Crane", crane_id=frappe.generate_hash(length=12), crane_name=self.key + " second", asset=self.asset.name)).insert()
		self.asset.asset_quantity = 2
		with self.assertRaisesRegex(frappe.ValidationError, "quantity 1"):
			self.asset.save()

	def test_company_mismatch_rejected_from_crane_and_native_asset(self):
		self.sharing()
		self.link()
		other = frappe.db.get_value("Company", {"name": ["!=", self.company.name]}, "name")
		self.asset.company = other
		self.asset.cost_center = frappe.get_cached_value("Company", other, "cost_center")
		with self.assertRaisesRegex(frappe.ValidationError, "Agreement Company"):
			self.asset.save()

	def test_company_share_changes_immediately_without_repricing_asset(self):
		self.sharing()
		self.link()
		data = asset_summary(self.crane.name)
		self.assertEqual(data["shares"], [])
		self.assertEqual(data["company_ownership_percentage"], 25)
		self.assertEqual(data["book_value"], 80000)
		self.assertEqual(self.crane.asset_accounting_basis, "Company Interest Only")
		self.crane.agreement_effective_from = add_days(today(), 10)
		for row, ownership, profit in zip(self.crane.ownership_partners, (10, 90), (90, 10)):
			row.ownership_percentage, row.profit_percentage = ownership, profit
		self.crane.save()
		self.assertEqual(asset_summary(self.crane.name)["company_ownership_percentage"], 10)
		with patch("heavy_equipment_rental.crane_assets.today", return_value=add_days(today(), 11)):
			data = asset_summary(self.crane.name)
			self.assertEqual(data["company_ownership_percentage"], 10)
			self.assertEqual(data["book_value"], 80000)


	def test_link_corrections_are_audited_without_reversing_asset_accounting(self):
		self.asset.submit()
		self.link()
		counts = {dt: frappe.db.count(dt) for dt in ("GL Entry", "Journal Entry", "Payment Entry")}
		self.crane.asset = None
		self.crane.save(ignore_version=False)
		version = frappe.get_last_doc("Version", filters={"ref_doctype": "Crane", "docname": self.crane.name})
		self.assertIn(["asset", self.asset.name, ""], frappe.parse_json(version.data)["changed"])
		self.assertEqual(frappe.db.get_value("Asset", self.asset.name, "docstatus"), 1)
		self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})
		self.link()
		self.asset.cancel()
		self.assertEqual(asset_summary(self.crane.name)["docstatus"], 2)
		self.crane.asset = None
		self.crane.save()
		with self.assertRaisesRegex(frappe.ValidationError, "active Asset"):
			self.link()

	def test_no_company_ownership_disallows_even_third_party_asset_links(self):
		supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=self.key,
			supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
		self.crane.ownership_type, self.crane.supplier = "Rented", supplier.name
		with self.assertRaisesRegex(frappe.ValidationError, "positive Company ownership"):
			self.link()
		self.crane.reload()
		self.crane.ownership_type, self.crane.supplier = "Rented", supplier.name
		self.crane.save()
		self.assertFalse(self.crane.asset_accounting_basis)
		from heavy_equipment_rental.crane_assets import make_company_asset
		with self.assertRaisesRegex(frappe.ValidationError, "owns no percentage"):
			make_company_asset(self.crane.name)

	def test_zero_company_shared_interest_keeps_partners_but_no_asset(self):
		self.sharing()
		self.crane.agreement_effective_from = add_days(today(), -9)
		self.crane.ownership_partners[0].ownership_percentage = 0
		self.crane.ownership_partners[1].ownership_percentage = 100
		self.crane.save()
		self.assertFalse(self.crane.asset_accounting_basis)
		self.assertEqual(len(self.crane.ownership_partners), 2)
		with self.assertRaisesRegex(frappe.ValidationError, "positive Company ownership"):
			self.link()

	def test_migration_archives_full_shared_link_without_rewriting_asset(self):
		from heavy_equipment_rental.patches.company_assets_only import execute
		self.sharing()
		self.link()
		frappe.db.set_value("Crane", self.crane.name, "asset_accounting_basis", "Whole Crane")
		counts = {dt: frappe.db.count(dt) for dt in ("GL Entry", "Asset", "Journal Entry")}
		execute()
		self.crane.reload()
		self.assertFalse(self.crane.asset)
		self.assertEqual(frappe.parse_json(self.crane.legacy_asset_recognition)[0]["asset"], self.asset.name)
		self.assertEqual(self.asset.reload().gross_purchase_amount, 100000)
		archive = self.crane.legacy_asset_recognition
		execute()
		self.assertEqual(self.crane.reload().legacy_asset_recognition, archive)
		self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})


	def test_asset_draft_and_basis_follow_company_ownership(self):
		from heavy_equipment_rental.crane_assets import make_company_asset
		self.crane.sharing_company = self.company.name
		self.crane.asset_accounting_basis = "Company Interest Only"
		self.crane.save()
		self.assertEqual(self.crane.asset_accounting_basis, "Company Owned")
		draft = make_company_asset(self.crane.name)
		self.assertEqual((draft["company"], draft["asset_owner"], draft["asset_quantity"]), (self.company.name, "Company", 1))
		self.sharing()
		self.assertEqual(self.crane.asset_accounting_basis, "Company Interest Only")
		self.assertIn("25.0%", make_company_asset(self.crane.name)["asset_name"])

	def test_link_changes_and_financial_reads_require_permissions(self):
		from heavy_equipment_rental.crane_assets import validate_asset_link

		self.crane.asset = self.asset.name
		with patch("frappe.only_for", side_effect=frappe.PermissionError):
			with self.assertRaises(frappe.PermissionError):
				validate_asset_link(self.crane)
		self.crane.reload()
		self.link()
		original = frappe.permissions.has_permission
		with patch("frappe.permissions.has_permission", side_effect=lambda dt, *a, **kw: False if dt == "Asset" else original(dt, *a, **kw)):
			with self.assertRaises(frappe.PermissionError):
				asset_summary(self.crane.name)

	def test_legacy_unlinked_cranes_remain_saveable(self):
		self.crane.crane_name += " updated"
		self.crane.save()
		self.assertIsNone(asset_summary(self.crane.name))

	def test_native_depreciation_and_reversal_are_live_without_crane_save(self):
		self.asset.submit()
		self.link()
		modified = self.crane.modified
		journal = frappe.get_doc(dict(doctype="Journal Entry", voucher_type="Depreciation Entry",
			company=self.company.name, posting_date=today(), accounts=[
				dict(account=self.accounts["depreciation_expense_account"], debit_in_account_currency=1000,
					cost_center=self.company.cost_center, reference_type="Asset", reference_name=self.asset.name),
				dict(account=self.accounts["accumulated_depreciation_account"], credit_in_account_currency=1000,
					cost_center=self.company.cost_center, reference_type="Asset", reference_name=self.asset.name),
			])).insert()
		journal.submit()
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 79000)
		self.assertEqual(str(frappe.db.get_value("Crane", self.crane.name, "modified")), str(modified))
		journal.cancel()
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 80000)

	def test_default_finance_book_is_used_instead_of_first_book(self):
		from erpnext.assets.doctype.asset.depreciation import make_depreciation_entry

		books = [frappe.get_doc(dict(doctype="Finance Book", finance_book_name=self.key + str(i))).insert().name
			for i in range(3)]
		original_book = self.company.default_finance_book

		def restore_book():
			frappe.db.set_value("Company", self.company.name, "default_finance_book", original_book, update_modified=False)
			frappe.clear_document_cache("Company", self.company.name)

		self.addCleanup(restore_book)
		frappe.db.set_value("Company", self.company.name, "default_finance_book", books[1], update_modified=False)
		frappe.clear_document_cache("Company", self.company.name)
		self.asset.calculate_depreciation = 1
		self.asset.opening_accumulated_depreciation = 0
		self.asset.default_finance_book = books[1]
		self.asset.set("finance_books", [dict(finance_book=book, depreciation_method="Straight Line",
			frequency_of_depreciation=12, total_number_of_depreciations=periods,
			expected_value_after_useful_life=0, depreciation_start_date=today())
			for book, periods in zip(books, (5, 10))])
		self.asset.save().submit()
		self.link()
		for book in books[:2]:
			schedule = frappe.db.get_value("Asset Depreciation Schedule", dict(asset=self.asset.name,
				finance_book=book, docstatus=1), "name")
			make_depreciation_entry(schedule, today())
		self.asset.reload()
		self.assertNotEqual(self.asset.finance_books[0].value_after_depreciation,
			self.asset.finance_books[1].value_after_depreciation)
		self.assertEqual(asset_summary(self.crane.name)["book_value"],
			self.asset.finance_books[1].value_after_depreciation)
		self.assertEqual(asset_summary(self.crane.name)["finance_book"], books[1])
		# A missing default must not become zero or silently select another book.
		frappe.db.set_value("Company", self.company.name, "default_finance_book", books[2], update_modified=False)
		frappe.clear_document_cache("Company", self.company.name)
		self.assertIsNone(asset_summary(self.crane.name)["book_value"])

	def test_disposed_asset_blocks_booking_until_restored(self):
		from heavy_equipment_rental.rental_validation import validate_rental_asset
		from erpnext.assets.doctype.asset.depreciation import scrap_asset, restore_asset
		self.asset.submit()
		self.link()
		scrap_asset(self.asset.name, today())
		with self.assertRaisesRegex(frappe.ValidationError, "disposed"):
			frappe.get_doc(dict(doctype="Rental Contract", customer=frappe.db.get_value("Customer", {}, "name"),
				location=self.key, assigned_cranes=[dict(crane=self.crane.name, start_date=today(),
				expected_end_date=today(), rental_rate_unit="Day", rental_rate=1000)])).insert()
		restore_asset(self.asset.name)
		validate_rental_asset(self.crane.name)
		for status in ("Sold", "Scrapped", "Capitalized"):
			frappe.db.set_value("Asset", self.asset.name, "status", status)
			with self.assertRaises(frappe.ValidationError):
				validate_rental_asset(self.crane.name)
		frappe.db.set_value("Asset", self.asset.name, {"status": "Cancelled", "docstatus": 2})
		with self.assertRaises(frappe.ValidationError):
			validate_rental_asset(self.crane.name)

	def test_assignment_derives_asset_company(self):
		self.link()
		assignment = frappe.get_doc(dict(doctype="Rental Contract",
			customer=frappe.db.get_value("Customer", {}, "name"), location=self.key,
			assigned_cranes=[dict(crane=self.crane.name, start_date=today(), expected_end_date=today(),
				rental_rate_unit="Day", rental_rate=1000)])).insert()
		self.assertEqual(assignment.company, self.company.name)
