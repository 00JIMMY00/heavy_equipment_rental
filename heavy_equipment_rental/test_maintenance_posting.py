from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from heavy_equipment_rental import test_native_crane_workflow as fixtures
from heavy_equipment_rental.maintenance_posting import post_and_complete
from heavy_equipment_rental.crane_repairs import repair_expense_sources


class TestMaintenancePosting(FrappeTestCase):
    def assert_reported_cost(self, job, amount):
        from heavy_equipment_rental.heavy_equipment_rental.report.maintenance_and_downtime.maintenance_and_downtime import posted_costs
        self.assertEqual(posted_costs([job])[job.name], amount)

    job = fixtures.TestNativeCraneWorkflow.job
    gl = fixtures.TestNativeCraneWorkflow.gl

    def setUp(self):
        from frappe.utils import today, add_days
        self.key = 'HER repair ' + frappe.generate_hash(length=8)
        self.company = frappe.get_doc('Company', frappe.db.get_value('Company', {'enable_perpetual_inventory': 1}, 'name'))
        self.mode = frappe.get_doc(dict(doctype='Mode of Payment', mode_of_payment=self.key,
            type='Cash', accounts=[dict(company=self.company.name, default_account=self.company.default_cash_account)])).insert()
        settings = frappe.get_single('Heavy Equipment Rental Settings')
        settings.set('repair_defaults', [dict(company=self.company.name,
            expense_account=self.company.default_expense_account, mode_of_payment=self.mode.name)])
        settings.save()
        self.crane = frappe.get_doc(dict(doctype='Crane', crane_id=frappe.generate_hash(length=12), crane_name=self.key,
            sharing_company=self.company.name)).insert()
        self.warehouse = frappe.get_doc(dict(doctype='Warehouse', warehouse_name=self.key,
            company=self.company.name)).insert().name
        self.part = frappe.get_doc(dict(doctype='Item', item_code=self.key,
            item_group=frappe.db.get_value('Item Group', {'is_group': 0}, 'name'),
            stock_uom='Nos', is_stock_item=1, valuation_method='FIFO')).insert()
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
        self.receipt = make_stock_entry(item_code=self.part.name, qty=10, rate=25,
            company=self.company.name, to_warehouse=self.warehouse, posting_date=add_days(today(), -1))

    def repair(self, source='My Stock', qty=2):
        supplier = frappe.get_doc(dict(doctype='Supplier', supplier_name=self.key + frappe.generate_hash(length=4),
            supplier_type='Company', supplier_group=frappe.db.get_value('Supplier Group', {'is_group': 0}, 'name'))).insert()
        return self.job(repair_source=source, repair_supplier=supplier.name,
            repair_expense_account=self.company.default_expense_account,
            repair_cost_center=self.company.cost_center,
            repair_items=[dict(item_code=self.crane.item if source == 'External Service' else self.part.name,
                qty=qty, warehouse=self.warehouse, rate=40)])

    def test_my_stock_posts_once_and_locks_inputs(self):
        job = self.repair()
        post_and_complete(job.name)
        job.reload()
        self.assertEqual(job.status, 'Completed')
        self.assertEqual(self.gl('Stock Entry', job.repair_material_issue, 'Expense'), 50)
        self.assertFalse(job.repair_purchase_invoice)
        post_and_complete(job.name)
        self.assertEqual(frappe.db.count('Stock Entry', {'crane_maintenance': job.name}), 1)
        job.repair_items[0].qty = 3
        with self.assertRaisesRegex(frappe.ValidationError, 'Not allowed to change|inputs cannot change'):
            job.save()

    def test_external_parts_receive_then_issue_and_reverse(self):
        job = self.repair('External Parts')
        post_and_complete(job.name)
        job.reload()
        invoice = frappe.get_doc('Purchase Invoice', job.repair_purchase_invoice)
        issue = frappe.get_doc('Stock Entry', job.repair_material_issue)
        self.assertEqual((invoice.docstatus, issue.docstatus, invoice.update_stock), (1, 1, 1))
        self.assertEqual(frappe.db.get_value('Bin', {'item_code': self.part.name, 'warehouse': self.warehouse}, 'actual_qty'), 10)
        self.assertEqual(self.gl('Purchase Invoice', invoice.name, 'Expense'), 0)
        # The dedicated Maintenance warehouse consumes the newly purchased parts.
        self.assertEqual(self.gl('Stock Entry', issue.name, 'Expense'), 80)
        self.assertEqual(sum(r['expenses'] for r in repair_expense_sources(self.crane.name, self.company.name)), 80)
        with self.assertRaisesRegex(frappe.ValidationError, 'Cancel Crane Maintenance'):
            invoice.cancel()
        job.cancel()
        self.assertEqual(issue.reload().docstatus, 2)
        self.assertEqual(invoice.reload().docstatus, 2)
        self.assertEqual(frappe.db.get_value('Bin', {'item_code': self.part.name, 'warehouse': self.warehouse}, 'actual_qty'), 10)

    def test_external_service_has_no_stock_issue(self):
        job = self.repair('External Service')
        post_and_complete(job.name)
        job.reload()
        self.assertFalse(job.repair_material_issue)
        self.assertEqual(self.gl('Purchase Invoice', job.repair_purchase_invoice, 'Expense'), 80)

    def test_failure_after_purchase_rolls_back_all_documents(self):
        job = self.repair('External Parts')
        from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
        with patch.object(StockEntry, 'submit', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                post_and_complete(job.name)
        self.assertEqual(frappe.db.count('Purchase Invoice', {'crane_maintenance': job.name}), 0)
        self.assertEqual(frappe.db.count('Stock Entry', {'crane_maintenance': job.name}), 0)
        self.assertEqual(job.reload().status, 'In Progress')
        self.assertEqual(frappe.db.get_value('Bin', {'item_code': self.part.name, 'warehouse': self.warehouse}, 'actual_qty'), 10)

    def test_invalid_parts_and_direct_completion_are_rejected(self):
        job = self.repair()
        job.status = 'Completed'
        with self.assertRaisesRegex(frappe.ValidationError, 'Use Submit'):
            job.save()
        job.reload()
        job.repair_items[0].qty = -1
        job.save()
        with self.assertRaisesRegex(frappe.ValidationError, 'positive quantities'):
            post_and_complete(job.name)

    def test_link_tampering_is_rejected(self):
        job = self.repair()
        job.repair_material_issue = self.receipt.name
        with self.assertRaisesRegex(frappe.ValidationError, 'links cannot be edited'):
            job.save()

    def test_payment_defaults_full_and_partial_leaves_outstanding(self):
        for amount in (None, 30, 0):
            job = self.repair('External Service')
            if amount is not None:
                job.pay_full_amount = 0
                job.supplier_paid_amount = amount
                job.save()
            post_and_complete(job.name)
            job.reload()
            paid = 80 if amount is None else amount
            self.assertEqual(job.supplier_paid_amount, paid)
            self.assertEqual(frappe.db.get_value('Purchase Invoice', job.repair_purchase_invoice, 'outstanding_amount'), 80 - paid)
            if paid:
                payment = frappe.get_doc('Payment Entry', job.repair_payment_entry)
                self.assertEqual((payment.docstatus, payment.paid_amount), (1, paid))
                self.assertEqual(payment.references[0].allocated_amount, paid)
            else:
                self.assertFalse(job.repair_payment_entry)

    def test_payment_failure_reverses_purchase_issue_and_warehouse(self):
        job = self.repair('External Parts')
        from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
        with patch.object(PaymentEntry, 'submit', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                post_and_complete(job.name)
        for doctype in ('Stock Entry', 'Purchase Invoice'):
            self.assertEqual(frappe.db.count(doctype, {'crane_maintenance': job.name}), 0)
        self.assertEqual(job.reload().status, 'In Progress')

    def test_settings_account_and_automatic_warehouse(self):
        job = self.repair('External Parts')
        job.repair_expense_account = None
        for row in job.repair_items:
            row.warehouse = None
        job.save()
        self.assertEqual(job.repair_expense_account, self.company.default_expense_account)
        post_and_complete(job.name)
        job.reload()
        warehouse = frappe.get_doc('Warehouse', job.repair_items[0].warehouse)
        self.assertEqual((warehouse.warehouse_name, warehouse.company), ('Maintenance', self.company.name))
        self.assertEqual(frappe.db.get_value('Bin', {'item_code': self.part.name, 'warehouse': warehouse.name}, 'actual_qty'), 0)

    def test_overpayment_is_rejected_without_postings(self):
        job = self.repair('External Parts')
        job.pay_full_amount = 0
        job.supplier_paid_amount = 100
        job.save()
        with self.assertRaisesRegex(frappe.ValidationError, 'Paid Amount'):
            post_and_complete(job.name)
        self.assertEqual(frappe.db.count('Purchase Invoice', {'crane_maintenance': job.name}), 0)

    def test_manual_source_label_and_migration_preserve_documents(self):
        job = self.job()
        self.assertEqual(job.repair_source, 'Manual Documents')
        counts = {dt: frappe.db.count(dt) for dt in ('Stock Entry', 'Purchase Invoice', 'Payment Entry', 'GL Entry')}
        frappe.db.set_value('Crane Maintenance', job.name, 'repair_source', None, update_modified=False)
        from heavy_equipment_rental.patches.explicit_repair_source import execute
        execute()
        execute()
        self.assertEqual(job.reload().repair_source, 'Manual Documents')
        self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})

    def test_configured_warehouse_is_used(self):
        settings = frappe.get_single('Heavy Equipment Rental Settings')
        settings.repair_defaults[0].warehouse = self.warehouse
        settings.save()
        job = self.repair('External Parts')
        job.pay_full_amount = 0
        job.supplier_paid_amount = 0
        job.save()
        post_and_complete(job.name)
        job.reload()
        self.assertEqual(job.repair_items[0].warehouse, self.warehouse)
        self.assertEqual(self.gl('Stock Entry', job.repair_material_issue, 'Expense'), 50)

    def test_settings_reject_invalid_account_and_duplicate_company(self):
        settings = frappe.get_single('Heavy Equipment Rental Settings')
        settings.repair_defaults[0].expense_account = self.company.default_cash_account
        with self.assertRaisesRegex(frappe.ValidationError, 'enabled Expense account'):
            settings.save()
        settings.reload()
        settings.append('repair_defaults', dict(company=self.company.name,
            expense_account=self.company.default_expense_account))
        with self.assertRaisesRegex(frappe.ValidationError, 'one Maintenance Defaults'):
            settings.save()

    def test_capital_improvements_complete_from_all_three_sources(self):
        from heavy_equipment_rental.heavy_equipment_rental.doctype.crane.test_crane import TestCrane
        original = frappe.get_doc
        def company_doc(*args, **kwargs):
            if len(args) >= 2 and args[:2] == ('Company', 'cranes company'):
                args = ('Company', self.company.name, *args[2:])
            return original(*args, **kwargs)
        fixture = TestCrane()
        with patch('frappe.get_doc', side_effect=company_doc):
            fixture.setUp()
        fixture.asset.submit()
        fixture.link()
        self.crane = fixture.crane
        for source, amount in [('My Stock', 50), ('External Parts', 80), ('External Service', 80), ('Supplier Bill', 110)]:
            job = self.repair(source)
            if source == 'Supplier Bill':
                job.repair_method = 'Supplier Bill'
                job.append('repair_items', dict(item_code=self.crane.item, qty=1, rate=30))
            job.cost_treatment = 'Capitalize Improvement'
            job.capitalization_reason = 'Major improvement extends service life'
            job.save()
            before = fixture.asset.reload().additional_asset_cost
            from heavy_equipment_rental.asset_repair import RentalAssetRepair
            with patch.object(RentalAssetRepair, 'submit', side_effect=frappe.PermissionError):
                with self.assertRaises(frappe.PermissionError):
                    post_and_complete(job.name)
            self.assertEqual(frappe.db.count('Purchase Invoice', {'crane_maintenance': job.name}), 0)
            self.assertEqual(frappe.db.count('Asset Repair', {'crane_maintenance': job.name}), 0)
            self.assertEqual(fixture.asset.reload().additional_asset_cost, before)
            post_and_complete(job.name)
            job.reload()
            self.assertEqual(job.status, 'Completed')
            repair = frappe.get_doc('Asset Repair', {'crane_maintenance': job.name, 'docstatus': 1})
            self.assertEqual(repair.total_repair_cost, amount)
            self.assert_reported_cost(job, amount)
            if source == 'External Parts':
                from heavy_equipment_rental.crane_repairs import validate_native_document
                repair.purchase_invoice = job.repair_purchase_invoice
                with self.assertRaisesRegex(frappe.ValidationError, 'through stock consumption'):
                    validate_native_document(repair)
                repair.reload()
            self.assertEqual(fixture.asset.reload().additional_asset_cost, before + amount)
            self.assertEqual(list(repair_expense_sources(self.crane.name, self.company.name)), [])
            post_and_complete(job.name)
            self.assertEqual(frappe.db.count('Asset Repair', {'crane_maintenance': job.name}), 1)
            if source == 'External Service':
                later = self.repair('My Stock')
                later.cost_treatment = 'Capitalize Improvement'
                later.capitalization_reason = 'Later asset improvement'
                later.save(); later.submit()
                with self.assertRaisesRegex(frappe.ValidationError, 'Cancel later Asset Repairs'):
                    job.cancel()
                job.reload()
                self.assertEqual(job.docstatus, 1)
                self.assertEqual(frappe.db.get_value('Payment Entry', job.repair_payment_entry, 'docstatus'), 1)
                later.cancel()
            job.cancel()
            self.assertEqual(repair.reload().docstatus, 2)
            self.assertEqual(fixture.asset.reload().additional_asset_cost, before)

    def test_quick_repair_uses_settings_account_and_cancels(self):
        job = self.job(repair_method='Quick Repair', cost=125)
        job.submit()
        expense = frappe.get_doc('Grouped Expense', job.grouped_expense)
        self.assertEqual(expense.docstatus, 1)
        self.assertEqual(self.gl('Journal Entry', expense.items[0].journal_entry, 'Expense'), 125)
        self.assert_reported_cost(job, 125)
        self.assertEqual(frappe.db.get_value('Expense Entry Type', job.expense_type, 'account'), self.company.default_expense_account)
        job.cancel()
        self.assertEqual(expense.reload().docstatus, 2)

    def test_supplier_bill_mixes_parts_and_labour(self):
        job = self.repair('External Parts')
        job.repair_method = 'Supplier Bill'
        job.append('repair_items', dict(item_code=self.crane.item, qty=1, rate=30))
        job.save().submit()
        invoice = frappe.get_doc('Purchase Invoice', job.repair_purchase_invoice)
        issue = frappe.get_doc('Stock Entry', job.repair_material_issue)
        self.assertEqual(len(invoice.items), 2)
        self.assertEqual(len(issue.items), 1)
        self.assertEqual(issue.items[0].item_code, self.part.name)
        self.assertEqual(self.gl('Purchase Invoice', invoice.name, 'Expense'), 30)
        self.assertEqual(self.gl('Stock Entry', issue.name, 'Expense'), 80)
        self.assertEqual(job.supplier_paid_amount, 110)
        self.assert_reported_cost(job, 110)
        job.cancel()
        self.assertEqual(invoice.reload().docstatus, 2)
        self.assertEqual(issue.reload().docstatus, 2)
