from io import BytesIO
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days
from openpyxl import Workbook

from heavy_equipment_rental.consolidated_expenses import HEADERS, parse_template
from heavy_equipment_rental.consolidated_expenses_setup import seed_defaults


class TestConsolidatedExpenses(FrappeTestCase):
    def setUp(self):
        self.company = frappe.db.get_value('Company', {'is_group': 0}, 'name')
        self.employee = frappe.get_doc(dict(doctype='Employee', first_name='Batch Test Driver',
            company=self.company, date_of_joining='2020-01-01', date_of_birth='1990-01-01',
            gender='Male', status='Active')).insert().name
        seed_defaults()
        self.default = next(r for r in frappe.get_single('Heavy Equipment Rental Settings').expense_defaults if r.company == self.company)
        self.mode = frappe.db.get_value('Mode of Payment Account', {'company': self.company}, 'parent')
        self.crane = frappe.get_doc(dict(doctype='Crane', crane_name='Batch test ' + frappe.generate_hash(length=8), operational_condition='Operational')).insert()
        if not frappe.db.exists('Location', 'Batch test yard'):
            frappe.get_doc(dict(doctype='Location', location_name='Batch test yard')).insert()
        self.contract = frappe.get_doc(dict(doctype='Rental Contract', company=self.company,
            customer=frappe.db.get_value('Customer', {}, 'name'), location='Batch test yard',
            assigned_cranes=[dict(crane=self.crane.name, start_date=today(), expected_end_date=add_days(today(), 1), rental_rate_unit='Hour', rental_rate=100)])).insert()
        self.sheet = frappe.get_doc(dict(doctype='Crane Timesheet', assignment=self.contract.name,
            crane=self.crane.name, driver=self.employee, period_start=today(), period_end=today(),
            timesheet_entries=[dict(work_date=today(), start_time='08:00', end_time='16:00')])).insert()
        self.sheet.submit()

    def batch(self):
        return frappe.get_doc(dict(doctype='Consolidated Expense', company=self.company,
            crane=self.crane.name, crane_timesheet=self.sheet.name, employee=self.employee,
            mode_of_payment=self.mode, items=[
                dict(posting_date=today(), description='First cost', amount=125),
                dict(posting_date=add_days(today(), 1), description='Second cost', amount=75),
            ]))

    def test_posting_links_defaults_cancel_and_amend(self):
        batch = self.batch().insert()
        self.assertEqual(batch.total, 200)
        self.assertEqual(batch.items[0].expense_entry_type, self.default.expense_type)
        batch.submit()
        links = [r.expense_entry for r in batch.items]
        from heavy_equipment_rental.general_ledger import voucher_scope
        scope = voucher_scope(frappe._dict(company=batch.company, consolidated_expense=batch.name))
        self.assertEqual(scope, {('Journal Entry', frappe.db.get_value('Expense Entry', name, 'journal_entry')) for name in links})
        from heavy_equipment_rental.rental_expenses import expense_sources
        sources = list(expense_sources(batch.crane, batch.company))
        self.assertEqual(sum(s['expenses'] for _, s in sources), 200)
        for row in batch.items:
            expense = frappe.get_doc('Expense Entry', row.expense_entry)
            self.assertEqual(expense.crane_timesheet, self.sheet.name)
            self.assertEqual(expense.crane_assignment, self.contract.name)
            journal = frappe.get_doc('Journal Entry', expense.journal_entry)
            self.assertEqual(journal.posting_date, row.posting_date)
            self.assertEqual(journal.total_debit, row.amount)
            self.assertEqual(journal.total_credit, row.amount)
            self.assertEqual(journal.accounts[0].party, self.employee)
            with self.assertRaises(frappe.ValidationError):
                expense.cancel()
        batch.cancel()
        self.assertTrue(all(frappe.db.get_value('Expense Entry', name, 'docstatus') == 2 for name in links))
        amended = frappe.copy_doc(batch, ignore_no_copy=True)
        amended.docstatus = 0
        amended.amended_from = batch.name
        amended.insert()
        amended.submit()
        self.assertTrue(set(links).isdisjoint(r.expense_entry for r in amended.items))

    def test_row_overrides_and_invalid_input(self):
        batch = self.batch()
        alternate = frappe.get_doc(dict(doctype='Expense Entry Type', title='Batch override', company=self.company,
            account=frappe.db.get_value('Expense Entry Type', self.default.expense_type, 'account'))).insert()
        mode = frappe.get_doc(dict(doctype='Mode of Payment', mode_of_payment='Batch '+frappe.generate_hash(length=8),
            type='Cash', accounts=[dict(company=self.company, default_account=frappe.db.get_value('Mode of Payment Account',
                {'company': self.company, 'parent': self.mode}, 'default_account'))])).insert()
        batch.items[1].expense_entry_type = alternate.name
        batch.items[1].mode_of_payment = mode.name
        batch.insert().submit()
        expense = frappe.get_doc('Expense Entry', batch.items[1].expense_entry)
        self.assertEqual(expense.mode_of_payment, mode.name)
        self.assertEqual(expense.expenses[0].expense_entry_type, alternate.name)
        invalid = self.batch()
        invalid.items[1].amount = float('nan')
        with self.assertRaises(frappe.ValidationError):
            invalid.insert()

    def test_failure_rolls_back_entire_submission(self):
        batch = self.batch().insert()
        from heavy_equipment_rental.expenses import RentalExpenseEntry
        original = RentalExpenseEntry.on_submit
        count = 0
        def fail_second(expense):
            nonlocal count
            count += 1
            if count == 2:
                frappe.throw('Simulated posting failure')
            original(expense)
        before = frappe.db.count('Expense Entry')
        frappe.db.savepoint('batch_submit')
        with patch.object(RentalExpenseEntry, 'on_submit', fail_second):
            with self.assertRaises(frappe.ValidationError):
                batch.submit()
        frappe.db.rollback(save_point='batch_submit')
        self.assertEqual(frappe.db.count('Expense Entry'), before)
        self.assertEqual(batch.reload().docstatus, 0)
        self.assertFalse(any(row.expense_entry for row in batch.items))

    def test_closed_settlement_guard_is_used(self):
        batch = self.batch().insert()
        from heavy_equipment_rental import rental_expenses
        with patch.object(rental_expenses, 'guard_expense', side_effect=frappe.ValidationError('Closed settlement')):
            with self.assertRaises(frappe.ValidationError):
                batch.submit()

    def test_real_settlement_counts_rows_once_and_blocks_cancellation(self):
        import json
        from heavy_equipment_rental.billing import generate_sales_invoice
        from heavy_equipment_rental.timesheet_settlement import ensure_settlement
        owner = frappe.get_doc(dict(doctype='Shareholder', title='Batch owner ' + frappe.generate_hash(length=8), company=self.company)).insert()
        self.crane.update(dict(ownership_type='Shared Ownership', sharing_company=self.company, enable_profit_sharing=1,
            agreement_effective_from=today(), operating_percentage=10))
        self.crane.set('ownership_partners', [dict(shareholder=owner.name, ownership_percentage=100, profit_percentage=100)])
        self.crane.save()
        ensure_settlement(self.sheet)
        self.sheet.reload()
        batch = self.batch().insert()
        batch.submit()
        invoice = frappe.get_doc('Sales Invoice', generate_sales_invoice(timesheet=self.sheet.name)['name'])
        invoice.submit()
        settlement = frappe.get_doc('Crane Profit Settlement', self.sheet.reload().profit_settlement)
        self.assertEqual(settlement.docstatus, 1)
        sources = json.loads(settlement.source_snapshot)
        expense_sources = [s for s in sources if s['doctype'] == 'Expense Entry']
        self.assertEqual({s['name'] for s in expense_sources}, {r.expense_entry for r in batch.items})
        self.assertEqual(sum(s['expenses'] for s in expense_sources), 200)
        frappe.db.savepoint('closed_batch')
        with self.assertRaises(frappe.ValidationError):
            batch.cancel()
        frappe.db.rollback(save_point='closed_batch')
        self.assertEqual(batch.reload().docstatus, 1)
        self.assertTrue(all(frappe.db.get_value('Expense Entry', r.expense_entry, 'docstatus') == 1 for r in batch.items))
        self.sheet.reload().cancel()
        self.assertEqual(self.sheet.reload().docstatus, 2)
        self.assertEqual(invoice.reload().docstatus, 2)
        self.assertEqual(settlement.reload().docstatus, 2)
        self.assertEqual(batch.reload().docstatus, 2)
        self.assertTrue(all(frappe.db.get_value('Expense Entry', r.expense_entry, 'docstatus') == 2 for r in batch.items))


    def workbook(self, rows):
        book = Workbook()
        book.active.title = 'Expenses'
        book.active.append(HEADERS)
        for row in rows:
            book.active.append(row)
        output = BytesIO()
        book.save(output)
        return output.getvalue()

    def test_excel_template_validation(self):
        rows = parse_template(self.workbook([[today(), 'وقود', 100, 'عام', self.mode]]), self.company)
        self.assertEqual(rows[0]['expense_entry_type'], self.default.expense_type)
        self.assertEqual(rows[0]['amount'], 100)
        for amount in ('=2+3', -1, 'not a number'):
            with self.assertRaises(frappe.ValidationError):
                parse_template(self.workbook([[today(), 'Invalid', amount, None, None]]), self.company)
        with self.assertRaises(frappe.ValidationError):
            parse_template(self.workbook([[None, 'Invalid', 10, None, None]]), self.company)

    def test_seeding_preserves_selected_defaults(self):
        before = frappe.get_single('Heavy Equipment Rental Settings').as_dict().expense_defaults
        count = frappe.db.count('Account')
        seed_defaults()
        self.assertEqual(frappe.db.count('Account'), count)
        self.assertEqual(frappe.get_single('Heavy Equipment Rental Settings').as_dict().expense_defaults, before)
