"""Native ledgers prove stock consumption, capitalization and owner recoveries."""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from heavy_equipment_rental.crane_assets import asset_summary
from heavy_equipment_rental.crane_repairs import make_repair_document, repair_expense_sources
from heavy_equipment_rental.profit_sharing import collect_sources


class TestNativeCraneWorkflow(FrappeTestCase):
	def setUp(self):
		from heavy_equipment_rental.heavy_equipment_rental.doctype.crane import test_crane
		self.fixture = test_crane.TestCrane()
		self.fixture.setUp()
		self.crane, self.asset, self.company = self.fixture.crane, self.fixture.asset, self.fixture.company
		self.key = self.fixture.key
		self.asset.submit()
		self.fixture.link()
		self.warehouse = frappe.get_doc(dict(doctype="Warehouse", warehouse_name=self.key,
			company=self.company.name)).insert().name
		self.part = frappe.get_doc(dict(doctype="Item", item_code=self.key + " spare", item_name="Repair part",
			item_group=frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
			stock_uom="Nos", is_stock_item=1, valuation_method="FIFO")).insert()
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
		self.receipt = make_stock_entry(item_code=self.part.name, qty=10, rate=25, company=self.company.name,
			to_warehouse=self.warehouse, posting_date=add_days(today(), -1))

	def job(self, treatment="Operating Expense", **kwargs):
		return frappe.get_doc(dict(doctype="Crane Maintenance", crane=self.crane.name,
			company=self.company.name, cost_treatment=treatment, maintenance_type="Corrective",
			status="In Progress", actual_start_date=today(), actual_end_date=today(),
			description="Native repair test", capitalization_reason="Major replacement extends future benefit",
			**kwargs)).insert()

	def issue(self, job, qty=2):
		doc = frappe.get_doc(make_repair_document(job.name, "Stock Entry"))
		doc.append("items", dict(item_code=self.part.name, s_warehouse=self.warehouse, qty=qty,
			expense_account=self.company.default_expense_account, cost_center=self.company.cost_center))
		doc.insert().submit()
		return doc

	def service_invoice(self, job, amount=100):
		supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=self.key + " service " + frappe.generate_hash(length=4),
			supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
		invoice = frappe.get_doc(make_repair_document(job.name, "Purchase Invoice"))
		invoice.supplier = supplier.name
		invoice.append("items", dict(item_code=self.crane.item, qty=1, rate=amount,
			expense_account=self.company.default_expense_account, cost_center=self.company.cost_center))
		invoice.insert().submit()
		return invoice

	def gl(self, doctype, name, root):
		return flt(sum(flt(r.debit) - flt(r.credit) for r in frappe.get_all("GL Entry",
			filters={"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
			fields=["account", "debit", "credit"])
			if frappe.get_cached_value("Account", r.account, "root_type") == root), 2)

	def test_stock_repair_expenses_once_without_increasing_asset(self):
		before = asset_summary(self.crane.name)["book_value"]
		job = self.job()
		entry = self.issue(job)
		self.assertEqual(self.gl("Stock Entry", entry.name, "Expense"), 50)
		self.assertEqual(asset_summary(self.crane.name)["book_value"], before)
		self.assertEqual(list(repair_expense_sources(self.crane.name, self.company.name))[0]["expenses"], 50)
		job.submit()
		self.assertFalse(job.expense_entry)
		self.assertEqual(self.crane.reload().operational_condition, "Operational")
		job.cancel()
		self.assertEqual(list(repair_expense_sources(self.crane.name, self.company.name)), [])
		self.assertEqual(frappe.db.get_value("Bin", {"item_code": self.part.name, "warehouse": self.warehouse}, "actual_qty"), 10)

	def test_capital_improvement_uses_actual_stock_value_and_reverses_together(self):
		job = self.job("Capitalize Improvement")
		repair = frappe.get_doc(make_repair_document(job.name, "Asset Repair"))
		repair.stock_consumption = 1
		# Deliberately wrong preview rate: native stock valuation is authoritative.
		repair.append("stock_items", dict(item_code=self.part.name, warehouse=self.warehouse,
			consumed_quantity=2, valuation_rate=999))
		repair.insert().submit()
		self.assertEqual(repair.total_repair_cost, 50)
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 80050)
		self.assertEqual(self.asset.reload().additional_asset_cost, 50)
		self.assertEqual(self.gl("Asset Repair", repair.name, "Asset"), 50)
		self.assertEqual(self.gl("Asset Repair", repair.name, "Expense"), -50)
		self.assertEqual(list(repair_expense_sources(self.crane.name, self.company.name)), [])
		stock = frappe.get_doc("Stock Entry", {"asset_repair": repair.name})
		with self.assertRaisesRegex(frappe.ValidationError, "Cancel the Asset Repair"):
			stock.cancel()
		repair.cancel()
		self.assertEqual(self.asset.reload().additional_asset_cost, 0)
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 80000)
		self.assertEqual(stock.reload().docstatus, 2)
		self.assertEqual(frappe.db.get_value("Bin", {"item_code": self.part.name, "warehouse": self.warehouse}, "actual_qty"), 10)

	def test_owner_recovery_consumes_parts_and_is_not_rental_profit(self):
		customer = frappe.db.get_value("Customer", {}, "name")
		job = self.job("Recover from Owner", owner_customer=customer)
		invoice = frappe.get_doc(make_repair_document(job.name, "Sales Invoice"))
		invoice.append("items", dict(item_code=self.part.name, warehouse=self.warehouse,
			qty=2, rate=40, income_account=self.company.default_income_account,
			expense_account=self.company.default_expense_account, cost_center=self.company.cost_center))
		invoice.insert().submit()
		self.assertEqual((invoice.grand_total, invoice.outstanding_amount), (80, 80))
		self.assertEqual(self.gl("Sales Invoice", invoice.name, "Expense"), 50)
		self.assertEqual(collect_sources(self.crane.name, self.company.name, today(), today()), [])
		self.assertEqual(self.asset.reload().additional_asset_cost, 0)
		job.submit()
		job.cancel()
		self.assertEqual(frappe.db.get_value("Bin", {"item_code": self.part.name, "warehouse": self.warehouse}, "actual_qty"), 10)

	def test_custody_crane_can_consume_stock_but_cannot_capitalize(self):
		supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=self.key,
			supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
		self.crane.asset = None
		self.crane.ownership_type, self.crane.supplier = "Rented", supplier.name
		self.crane.asset_accounting_basis = "Third-party Custody"
		self.crane.save()
		self.assertEqual(self.gl("Stock Entry", self.issue(self.job()).name, "Expense"), 50)
		with self.assertRaisesRegex(frappe.ValidationError, "Link the reviewed native Asset"):
			self.job("Capitalize Improvement")

	def test_shared_service_product_and_company_interest_values(self):
		other = frappe.get_doc(dict(doctype="Crane", crane_name=self.key + " other")).insert()
		self.assertEqual(other.item, self.crane.item)
		self.assertNotEqual(self.asset.item_code, self.crane.item)
		self.crane.asset_accounting_basis = "Company Interest Only"
		self.crane.save()
		self.assertEqual(asset_summary(self.crane.name)["shares"], [])
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 80000)

	def test_external_service_costs_and_capitalization_are_not_duplicated(self):
		operating_job = self.job()
		service = self.service_invoice(operating_job)
		sources = collect_sources(self.crane.name, self.company.name, today(), today())
		self.assertEqual([(s["name"], s["expenses"]) for s in sources], [(service.name, 100)])
		capital_job = self.job("Capitalize Improvement")
		capital_invoice = self.service_invoice(capital_job, 200)
		repair = frappe.get_doc(make_repair_document(capital_job.name, "Asset Repair"))
		repair.purchase_invoice = capital_invoice.name
		repair.insert().submit()
		self.assertEqual((repair.repair_cost, repair.total_repair_cost), (200, 200))
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 80200)
		self.assertEqual(self.gl("Asset Repair", repair.name, "Asset"), 200)
		self.assertEqual(sum(s["expenses"] for s in collect_sources(self.crane.name, self.company.name, today(), today())), 100)
		with self.assertRaises(frappe.ValidationError):
			capital_invoice.cancel()
		repair.cancel()
		capital_invoice.reload().cancel()
		self.assertEqual(asset_summary(self.crane.name)["book_value"], 80000)

	def test_repair_costs_appear_in_posting_date_profitability(self):
		from heavy_equipment_rental.heavy_equipment_rental.report.crane_rental_profitability.crane_rental_profitability import execute
		entry = self.issue(self.job())
		result = execute(dict(company=self.company.name, crane=self.crane.name, from_date=today(), to_date=today()))
		self.assertEqual([row["value"] for row in result[4]], [0, 50, -50])
		self.assertEqual(result[1][0]["voucher"], entry.name)

	def test_shared_item_keeps_two_cranes_separate_on_one_invoice(self):
		from heavy_equipment_rental.billing import generate_sales_invoice
		from heavy_equipment_rental.heavy_equipment_rental.report.crane_rental_profitability.crane_rental_profitability import execute

		other = frappe.get_doc(dict(doctype="Crane", crane_name=self.key + " second crane")).insert()
		assignment = frappe.get_doc(dict(doctype="Crane Assignment", company=self.company.name,
			customer=frappe.db.get_value("Customer", {}, "name"), location=self.key,
			assigned_cranes=[dict(crane=crane, start_date=today(), expected_end_date=today(),
				rental_rate_unit="Hour", rental_rate=rate) for crane, rate in ((self.crane.name, 1000), (other.name, 500))])).insert()
		for crane, hour in ((self.crane.name, 8), (other.name, 12)):
			frappe.get_doc(dict(doctype="Crane Timesheet", assignment=assignment.name, crane=crane,
				period_start=today(), period_end=today(), driver=frappe.db.get_value("Employee", {"company": self.company.name}, "name"),
				timesheet_entries=[dict(work_date=today(), start_time=f"{hour:02}:00", end_time=f"{hour+2:02}:00")])).insert().submit()
		invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(assignment=assignment.name)["name"])
		invoice.submit()
		self.assertEqual(len({row.item_code for row in invoice.items}), 1)
		for crane, amount in ((self.crane.name, 2000), (other.name, 1000)):
			sources = collect_sources(crane, self.company.name, today(), today())
			self.assertEqual(sum(source.get("revenue", 0) for source in sources), amount)
			result = execute(dict(company=self.company.name, crane=crane, from_date=today(), to_date=today()))
			self.assertEqual(result[4][0]["value"], amount)

	def test_improvement_regenerates_native_depreciation_schedule(self):
		asset = frappe.copy_doc(self.asset)
		asset.docstatus = 0
		asset.asset_name = self.key + " scheduled"
		asset.calculate_depreciation = 1
		asset.opening_accumulated_depreciation = 0
		asset.set("finance_books", [dict(depreciation_method="Straight Line", frequency_of_depreciation=12,
			total_number_of_depreciations=5, expected_value_after_useful_life=0,
			depreciation_start_date=add_days(today(), 30))])
		asset.insert().submit()
		self.crane.asset = asset.name
		self.crane.save()
		old_schedule = frappe.db.get_value("Asset Depreciation Schedule", {"asset": asset.name, "status": "Active"}, "name")
		repair = frappe.get_doc(make_repair_document(self.job("Capitalize Improvement").name, "Asset Repair"))
		repair.stock_consumption = 1
		repair.append("stock_items", dict(item_code=self.part.name, warehouse=self.warehouse, consumed_quantity=2, valuation_rate=1))
		repair.insert().submit()
		self.assertEqual(asset.reload().finance_books[0].value_after_depreciation, 100050)
		new_schedule = frappe.db.get_value("Asset Depreciation Schedule", {"asset": asset.name, "status": "Active"}, "name")
		self.assertNotEqual(old_schedule, new_schedule)
		repair.cancel()
		self.assertEqual(asset.reload().finance_books[0].value_after_depreciation, 100000)

	def test_serialized_improvement_restores_stock_on_cancellation(self):
		from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
		from erpnext.stock.doctype.serial_and_batch_bundle.test_serial_and_batch_bundle import make_serial_batch_bundle

		part = frappe.get_doc(dict(doctype="Item", item_code=self.key + " serialized",
			item_group=self.part.item_group, stock_uom="Nos", is_stock_item=1, has_serial_no=1,
			serial_no_series="HER-" + frappe.generate_hash(length=5) + "-.####")).insert()
		make_stock_entry(item_code=part.name, qty=1, rate=75, company=self.company.name,
			to_warehouse=self.warehouse, posting_date=add_days(today(), -1))
		serials = frappe.get_all("Serial No", filters={"item_code": part.name}, pluck="name")
		bundle = make_serial_batch_bundle(dict(item_code=part.name, warehouse=self.warehouse,
			company=self.company.name, qty=-1, voucher_type="Asset Repair", type_of_transaction="Asset Repair",
			serial_nos=serials, posting_date=today(), do_not_submit=1))
		repair = frappe.get_doc(make_repair_document(self.job("Capitalize Improvement").name, "Asset Repair"))
		repair.stock_consumption = 1
		repair.append("stock_items", dict(item_code=part.name, warehouse=self.warehouse, consumed_quantity=1,
			valuation_rate=75, serial_and_batch_bundle=bundle.name))
		repair.insert().submit()
		self.assertEqual(self.asset.reload().additional_asset_cost, 75)
		repair.cancel()
		self.assertEqual(self.asset.reload().additional_asset_cost, 0)
		self.assertEqual(frappe.db.get_value("Bin", {"item_code": part.name, "warehouse": self.warehouse}, "actual_qty"), 1)

	def test_native_permission_and_attribution_checks(self):
		job = self.job()
		original = frappe.has_permission
		with patch("frappe.has_permission", side_effect=lambda dt, *a, **kw:
			(_ for _ in ()).throw(frappe.PermissionError) if dt == "Stock Entry" else original(dt, *a, **kw)):
			with self.assertRaises(frappe.PermissionError):
				make_repair_document(job.name, "Stock Entry")
		entry = frappe.get_doc(make_repair_document(job.name, "Stock Entry"))
		entry.crane = frappe.get_doc(dict(doctype="Crane", crane_name=self.key + " wrong")).insert().name
		entry.append("items", dict(item_code=self.part.name, s_warehouse=self.warehouse, qty=1))
		with self.assertRaisesRegex(frappe.ValidationError, "does not match"):
			entry.insert()

	def test_review_settlement_includes_repair_and_posts_selected_expense(self):
		self.crane.update(dict(ownership_type="Shared Ownership", sharing_company=self.company.name,
			agreement_effective_from=today(), operating_percentage=10,
			settlement_approval="Review Before Posting", distribution_posting="Partner Expense",
			settlement_revenue_basis="Net Revenue", include_depreciation=1,
			profit_allocation_account=self.company.default_expense_account))
		owner = frappe.get_doc(dict(doctype="Shareholder", title=self.key + " partner", company=self.company.name)).insert()
		self.crane.set("ownership_partners", [dict(is_company=1, ownership_percentage=50, profit_percentage=50),
			dict(shareholder=owner.name, ownership_percentage=50, profit_percentage=50)])
		self.crane.save()
		sheet = frappe.get_doc(dict(doctype="Crane Timesheet", crane=self.crane.name,
			customer=frappe.db.get_value("Customer", {}, "name"), location=self.key,
			period_start=today(), period_end=today(), rental_rate_unit="Hour", rental_rate=1000,
			driver=frappe.db.get_value("Employee", {"company": self.company.name}, "name"),
			timesheet_entries=[dict(work_date=today(), start_time="08:00", end_time="10:00")])).insert()
		sheet.submit()
		from heavy_equipment_rental.billing import generate_sales_invoice
		invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=sheet.name)["name"])
		tax_account = frappe.get_doc(dict(doctype="Account", account_name=self.key + " VAT",
			company=self.company.name, account_type="Tax", parent_account=frappe.db.get_value(
				"Account", {"company": self.company.name, "root_type": "Liability", "is_group": 1}, "name"))).insert()
		invoice.append("taxes", dict(charge_type="Actual", account_head=tax_account.name, tax_amount=200, description="Test VAT"))
		invoice.save()
		invoice.submit()
		self.assertEqual(invoice.grand_total, 2200)
		settlement = frappe.get_doc("Crane Profit Settlement", sheet.reload().profit_settlement)
		self.assertEqual(settlement.docstatus, 0)
		job = self.job(crane_timesheet=sheet.name, crane_assignment=sheet.assignment)
		entry = self.issue(job)
		depreciation = frappe.get_doc(dict(doctype="Journal Entry", voucher_type="Depreciation Entry",
			company=self.company.name, posting_date=today(), accounts=[
				dict(account=self.fixture.accounts["depreciation_expense_account"], debit_in_account_currency=100,
					cost_center=self.company.cost_center, reference_type="Asset", reference_name=self.asset.name),
				dict(account=self.fixture.accounts["accumulated_depreciation_account"], credit_in_account_currency=100,
					cost_center=self.company.cost_center, reference_type="Asset", reference_name=self.asset.name),
			])).insert()
		depreciation.submit()
		settlement.save()
		self.assertEqual((settlement.revenue, settlement.operating_expenses, settlement.external_distribution), (2000, 150, 825))
		with self.assertRaisesRegex(frappe.ValidationError, "Costs Reviewed"):
			settlement.submit()
		settlement.reload()
		settlement.costs_reviewed = 1
		with self.assertRaisesRegex(frappe.ValidationError, "Complete or cancel repair"):
			settlement.submit()
		job.submit()
		settlement.reload()
		settlement.costs_reviewed = 1
		settlement.submit()
		journal = frappe.get_doc("Journal Entry", settlement.journal_entry)
		self.assertEqual(journal.accounts[0].account, self.company.default_expense_account)
		self.assertEqual(journal.total_debit, 825)
		# Funding changes cash/equity, not the closed rental result.
		equity = frappe.get_doc(dict(doctype="Account", account_name=self.key + " funding",
			company=self.company.name, parent_account=frappe.db.get_value("Account",
				{"company": self.company.name, "root_type": "Equity", "is_group": 1}, "name"))).insert()
		funding = frappe.get_doc(dict(doctype="Journal Entry", company=self.company.name, posting_date=today(),
			accounts=[dict(account=self.company.default_cash_account, crane=self.crane.name, debit_in_account_currency=100),
				dict(account=equity.name, crane=self.crane.name, credit_in_account_currency=100)])).insert()
		funding.submit()
		self.assertEqual(funding.docstatus, 1)
		with self.assertRaises(frappe.ValidationError):
			entry.cancel()
		self.assertEqual(json.loads(settlement.agreement_snapshot)["distribution_posting"], "Partner Expense")

	def test_migration_repeat_does_not_change_new_terms_or_post_ledgers(self):
		from heavy_equipment_rental.patches.crane_native_workflow import execute
		counts = {dt: frappe.db.count(dt) for dt in ("GL Entry", "Asset", "Sales Invoice", "Stock Entry")}
		execute()
		execute()
		self.assertEqual(self.crane.reload().settlement_approval, "On Invoice Submission")
		self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})
