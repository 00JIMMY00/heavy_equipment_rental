"""Native submit/cancel/amend reverses the repair as one transaction."""
import json
from unittest.mock import patch
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today
from heavy_equipment_rental import test_maintenance_posting as fixtures
from heavy_equipment_rental.maintenance_cancellation import build_plan, cancel_with_plan


class TestMaintenanceLifecycle(FrappeTestCase):
    setUp = fixtures.TestMaintenancePosting.setUp
    repair = fixtures.TestMaintenancePosting.repair
    job = fixtures.TestMaintenancePosting.job
    gl = fixtures.TestMaintenancePosting.gl

    def amendment(self, job):
        amended = frappe.copy_doc(job)
        amended.docstatus = 0
        amended.amended_from = job.name
        amended.insert()
        self.assertEqual(amended.status, 'Planned')
        for field in ('repair_purchase_invoice', 'repair_material_issue', 'repair_payment_entry', 'expense_entry', 'grouped_expense'):
            self.assertFalse(amended.get(field))
        return amended

    def test_paid_parts_cancel_amend_with_changed_dates_and_amount(self):
        job = self.repair('External Parts')
        self.assertEqual(frappe.db.count('Purchase Invoice', {'crane_maintenance': job.name}), 0)
        job.submit()
        self.assertEqual((job.docstatus, job.status), (1, 'Completed'))
        links = (job.repair_purchase_invoice, job.repair_material_issue, job.repair_payment_entry)
        plan = build_plan(job.name)
        self.assertEqual([r['doctype'] for r in plan], ['Payment Entry','Stock Entry','Purchase Invoice','Crane Maintenance'])
        cancel_with_plan(job.name, json.dumps(plan))
        job.reload()
        self.assertEqual((job.docstatus, job.status), (2, 'Cancelled'))
        for dt, name in zip(('Purchase Invoice', 'Stock Entry', 'Payment Entry'), links):
            self.assertEqual(frappe.db.get_value(dt, name, 'docstatus'), 2)
        self.assertEqual(self.receipt.reload().docstatus, 1)
        amended = self.amendment(job)
        amended.actual_start_date = amended.actual_end_date = add_days(today(), 1)
        amended.repair_items[0].qty = 3
        amended.pay_full_amount = 0
        amended.supplier_paid_amount = 30
        amended.save()
        amended.submit()
        invoice = frappe.get_doc('Purchase Invoice', amended.repair_purchase_invoice)
        self.assertNotEqual(invoice.name, links[0])
        self.assertEqual(str(invoice.posting_date), add_days(today(), 1))
        self.assertEqual((invoice.grand_total, invoice.outstanding_amount), (120, 90))
        self.assertEqual(frappe.db.get_value('Crane Maintenance', job.name, 'actual_start_date').isoformat(), today())

    def test_stock_cancel_preserves_original_purchase_and_restores_qty(self):
        job = self.repair()
        job.submit()
        job.cancel()
        self.assertEqual(self.receipt.reload().docstatus, 1)
        self.assertEqual(frappe.db.get_value('Bin', {'item_code':self.part.name,'warehouse':self.warehouse}, 'actual_qty'), 10)
        self.amendment(job).submit()
        self.assertEqual(frappe.db.get_value('Bin', {'item_code':self.part.name,'warehouse':self.warehouse}, 'actual_qty'), 8)

    def test_failed_cancellation_rolls_back_prior_payment_cancellation(self):
        job = self.repair('External Parts')
        job.submit()
        from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
        with patch.object(StockEntry, 'cancel', side_effect=frappe.ValidationError('Closed period')):
            with self.assertRaisesRegex(frappe.ValidationError, 'Closed period'):
                job.cancel()
        self.assertEqual(job.reload().docstatus, 1)
        for dt, name in [('Payment Entry',job.repair_payment_entry),('Purchase Invoice',job.repair_purchase_invoice),('Stock Entry',job.repair_material_issue)]:
            self.assertEqual(frappe.db.get_value(dt,name,'docstatus'),1)

    def test_stale_preview_and_cancel_permission_denial(self):
        job = self.repair('External Service')
        job.submit()
        with self.assertRaisesRegex(frappe.ValidationError, 'Linked documents changed'):
            cancel_with_plan(job.name, '[]')
        from frappe.model.document import Document
        original = Document.check_permission
        def check(doc, permtype='read', *args, **kwargs):
            if doc.doctype == 'Payment Entry' and permtype == 'cancel':
                raise frappe.PermissionError
            return original(doc, permtype, *args, **kwargs)
        with patch.object(Document, 'check_permission', check):
            with self.assertRaises(frappe.PermissionError):
                job.cancel()
        self.assertEqual(job.reload().docstatus,1)
        self.assertEqual(frappe.db.get_value('Payment Entry',job.repair_payment_entry,'docstatus'),1)

    def test_migration_is_repeatable_without_reposting(self):
        job = self.repair('External Service')
        job.submit()
        frappe.db.set_value('Crane Maintenance', job.name, 'docstatus', 0, update_modified=False)
        modified = job.modified
        counts = {dt:frappe.db.count(dt) for dt in ('Purchase Invoice','Payment Entry','GL Entry')}
        from heavy_equipment_rental.patches.submittable_maintenance import execute
        execute(); execute()
        self.assertEqual(job.reload().docstatus,1)
        self.assertEqual(str(job.modified),str(modified))
        self.assertEqual(json.loads(job.legacy_lifecycle)['docstatus'],0)
        self.assertEqual(counts,{dt:frappe.db.count(dt) for dt in counts})
        job.cancel()
        self.amendment(job)

    def test_cash_expense_cancel_and_amend_reposts_journal(self):
        expense_type = frappe.get_doc(dict(doctype='Expense Entry Type', title=self.key,
            company=self.company.name, account=self.company.default_expense_account, enabled=1))
        expense_type.insert()
        job = self.job('Cash Expense', expense_type=expense_type.name, mode_of_payment=self.mode.name, cost=125)
        job.submit()
        expense = frappe.get_doc('Grouped Expense', job.grouped_expense)
        journal = expense.items[0].journal_entry
        self.assertIn(dict(doctype='Journal Entry',name=journal),build_plan(job.name))
        job.cancel()
        self.assertEqual(expense.reload().docstatus,2)
        self.assertEqual(frappe.db.get_value('Journal Entry',journal,'docstatus'),2)
        amended = self.amendment(job)
        amended.cost=150
        amended.submit()
        self.assertNotEqual(amended.grouped_expense,expense.name)
        self.assertEqual(frappe.get_doc('Grouped Expense',amended.grouped_expense).items[0].amount,150)

    def test_new_record_cannot_claim_existing_generated_links(self):
        data = dict(doctype='Crane Maintenance',crane=self.crane.name,company=self.company.name,
            maintenance_type='Corrective',description='Forged link',repair_source='My Stock',
            cost_treatment='Operating Expense',repair_material_issue=self.receipt.name)
        with self.assertRaisesRegex(frappe.ValidationError,'cannot be supplied'):
            frappe.get_doc(data).insert()

    def test_combined_payment_requires_separate_resolution(self):
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
        first = self.repair('External Service')
        first.pay_full_amount=0
        first.supplier_paid_amount=0
        first.save(); first.submit()
        second = self.repair('External Service')
        second.repair_supplier=first.repair_supplier
        second.pay_full_amount=0
        second.supplier_paid_amount=0
        second.save(); second.submit()
        payment=get_payment_entry('Purchase Invoice',first.repair_purchase_invoice,
            bank_account=self.company.default_cash_account,party_amount=160,bank_amount=160)
        payment.references[0].allocated_amount=80
        payment.append('references',dict(reference_doctype='Purchase Invoice',reference_name=second.repair_purchase_invoice,
            total_amount=80,outstanding_amount=80,allocated_amount=80))
        payment.insert().submit()
        with self.assertRaisesRegex(frappe.ValidationError,'outside this repair'):
            first.cancel()
        self.assertEqual(first.reload().docstatus,1)
        self.assertEqual(second.reload().docstatus,1)
        self.assertEqual(payment.reload().docstatus,1)


    def test_submitted_repair_rejects_new_manual_documents(self):
        from heavy_equipment_rental.crane_repairs import make_repair_document
        job=self.repair('External Service')
        job.submit()
        with self.assertRaisesRegex(frappe.ValidationError,'Cancel and amend'):
            make_repair_document(job.name,'Purchase Invoice')
        with self.assertRaisesRegex(frappe.ValidationError,'Use Submit'):
            frappe.get_doc(dict(doctype='Crane Maintenance',crane=self.crane.name,company=self.company.name,
                repair_source='Manual Documents',cost_treatment='No Cost',maintenance_type='Inspection',
                description='No bypass',status='Completed')).insert()

    def test_multiple_manual_asset_repairs_reverse_newest_first(self):
        from heavy_equipment_rental.heavy_equipment_rental.doctype.crane.test_crane import TestCrane
        from heavy_equipment_rental.crane_repairs import make_repair_document
        original=frappe.get_doc
        def get_doc(*args, **kwargs):
            if len(args)>=2 and args[:2]==('Company','cranes company'):
                args=('Company',self.company.name,*args[2:])
            return original(*args,**kwargs)
        fixture=TestCrane()
        with patch('frappe.get_doc',side_effect=get_doc): fixture.setUp()
        fixture.asset.submit(); fixture.link()
        self.crane=fixture.crane
        job=self.job('Capitalize Improvement')
        repairs=[]
        for _ in range(2):
            repair=frappe.get_doc(make_repair_document(job.name,'Asset Repair'))
            repair.stock_consumption=1
            repair.append('stock_items',dict(item_code=self.part.name,warehouse=self.warehouse,consumed_quantity=1,valuation_rate=25))
            repair.insert().submit()
            repairs.append(repair)
        job.submit()
        self.assertEqual([r['name'] for r in build_plan(job.name) if r['doctype']=='Asset Repair'],[r.name for r in reversed(repairs)])
        job.cancel()
        self.assertEqual(fixture.asset.reload().additional_asset_cost,0)
        self.assertTrue(all(r.reload().docstatus==2 for r in repairs))
