"""Reconcile the payment statement with real GL postings and source permissions."""

from unittest.mock import patch

import frappe
import frappe.permissions
from heavy_equipment_rental.test_expenses import legacy_expense
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from heavy_equipment_rental.heavy_equipment_rental.report.mode_of_payment_statement.mode_of_payment_statement import execute


class TestModeOfPaymentStatement(FrappeTestCase):
    def setUp(self):
        from heavy_equipment_rental.test_expenses import enable_historical_fixtures
        enable_historical_fixtures(self)
        from heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.test_treasury_transaction import TestTreasuryTransaction

        self.fixture = TestTreasuryTransaction()
        self.fixture.setUp()
        self.company = self.fixture.company
        self.cash, self.bank = self.fixture.accounts
        self.mode = self.fixture.mode
        self.bank_mode = frappe.get_doc(dict(
            doctype='Mode of Payment', mode_of_payment='Statement bank ' + self.fixture.key,
            type='Bank', accounts=[dict(company=self.company, default_account=self.bank)],
        )).insert()
        self.filters = dict(company=self.company, from_date=today(), to_date=today(),
                            mode_of_payment=self.mode.name)
        self.income = frappe.db.get_value('Company', self.company, 'default_income_account')

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()

    def report(self, **values):
        return execute(dict(self.filters, **values))

    def journal(self, amount, posting_date=None, submit=True):
        doc = frappe.get_doc(dict(
            doctype='Journal Entry', company=self.company,
            posting_date=posting_date or today(), user_remark='Statement funding',
            accounts=[dict(account=self.cash, debit_in_account_currency=amount),
                      dict(account=self.income, credit_in_account_currency=amount)],
        )).insert()
        if submit:
            doc.submit()
        return doc

    def test_opening_transfers_running_balances_and_chart(self):
        self.journal(1000, add_days(today(), -1))
        self.fixture.transaction(amount=200, description='Move to bank').insert().submit()
        self.fixture.transaction(amount=75, posting_date=add_days(today(), 1)).insert().submit()
        result = self.report(mode_of_payment=None)
        columns, rows, message, chart, summary, skip_total = result
        relevant = [r for r in rows if r['account'] in (self.cash, self.bank)]
        self.assertEqual([r['balance'] for r in relevant if r['account'] == self.cash], [1000, 800])
        self.assertEqual([r['balance'] for r in relevant if r['account'] == self.bank], [0, 200])
        self.assertEqual(sum(r['incoming'] for r in relevant), 200)
        self.assertEqual(sum(r['outgoing'] for r in relevant), 200)
        for mode, expected in ((self.mode.name, [0, 200, 800]), (self.bank_mode.name, [200, 0, 200])):
            index = chart['data']['labels'].index(mode)
            self.assertEqual([series['values'][index] for series in chart['data']['datasets']], expected)
        selected = self.report()
        self.assertEqual([s['value'] for s in selected[4]], [1000, 0, 200, 800])
        self.assertEqual(selected[1][-1]['remarks'], 'Move to bank')
        self.assertTrue(skip_total)
        self.assertEqual([c['fieldname'] for c in columns if not c.get('hidden')], [
            'posting_date', 'payment_modes', 'incoming', 'outgoing', 'balance', 'remarks', 'voucher',
        ])

    def test_native_payment_entry_and_cancellation(self):
        payment = frappe.get_doc(dict(
            doctype='Payment Entry', payment_type='Internal Transfer', company=self.company,
            posting_date=today(), mode_of_payment=self.mode.name,
            paid_from=self.cash, paid_to=self.bank, paid_amount=50, received_amount=50,
            source_exchange_rate=1, target_exchange_rate=1, reference_no='statement-test',
            reference_date=today(), custom_remarks=1, remarks='Native payment description',
        )).insert().submit()
        rows = self.report()[1]
        self.assertEqual(rows[-1]['outgoing'], 50)
        self.assertEqual(rows[-1]['remarks'], 'Native payment description')
        self.assertEqual(rows[-1]['voucher'], payment.name)
        self.assertEqual(self.report(mode_of_payment=self.bank_mode.name)[1][-1]['incoming'], 50)
        payment.cancel()
        self.assertEqual([r['balance'] for r in self.report()[1]], [0])

    def test_shared_modes_are_counted_once_in_all_modes_and_filter(self):
        alias = frappe.copy_doc(self.mode)
        alias.mode_of_payment = 'Statement alias ' + self.fixture.key
        alias.insert()
        self.journal(90)
        for selected in (self.mode.name, alias.name, None):
            rows = [r for r in self.report(mode_of_payment=selected)[1] if r['account'] == self.cash]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]['incoming'], 90)
            self.assertEqual(rows[-1]['balance'], 90)
            self.assertIn(alias.name, rows[-1]['payment_modes'])
            self.assertIn(self.mode.name, rows[-1]['payment_modes'])

    def test_drafts_cancelled_and_disabled_history(self):
        self.journal(700, submit=False)
        cancelled = self.journal(120)
        cancelled.cancel()
        self.journal(45)
        self.mode.enabled = 0
        self.mode.save()
        frappe.db.set_value('Account', self.cash, 'disabled', 1)
        self.assertEqual([s['value'] for s in self.report()[4]], [0, 45, 0, 45])

    def test_normal_and_grouped_expense_descriptions_without_double_count(self):
        from heavy_equipment_rental.test_consolidated_expenses import TestGroupedExpenses

        fixture = TestGroupedExpenses()
        fixture.setUp()
        batch = fixture.batch()
        batch.mode_of_payment = self.mode.name
        for row in batch.items:
            row.posting_date = today()
        batch.insert().submit()
        normal = legacy_expense(batch, batch.items[0])
        normal.description = 'Ordinary expense remarks'
        normal.insert().submit()
        rows = self.report()[1]
        self.assertEqual(sum(r['outgoing'] for r in rows), 325)
        self.assertEqual({r['remarks'] for r in rows if not r.get('is_opening')},
                         {'First cost', 'Second cost', 'Ordinary expense remarks'})
        self.assertEqual(sum(r['voucher'] == batch.name for r in rows if r.get('voucher')), 2)

    def test_legacy_grouped_expense_description_and_permissions(self):
        from heavy_equipment_rental.test_consolidated_expenses import TestGroupedExpenses

        fixture = TestGroupedExpenses()
        fixture.setUp()
        batch = fixture.batch()
        batch.mode_of_payment = self.mode.name
        for row in batch.items:
            row.posting_date = today()
        batch.insert()
        for row in batch.items:
            expense = legacy_expense(batch, row).insert().submit()
            row.db_set('expense_entry', expense.name)
            row.db_set('docstatus', 1)
        batch.db_set('docstatus', 1)
        self.assertEqual(sum(r['outgoing'] for r in self.report()[1]), 200)
        self.assertEqual({r['remarks'] for r in self.report()[1] if not r.get('is_opening')},
                         {'First cost', 'Second cost'})
        native = frappe.permissions.has_permission

        def permission(doctype, ptype='read', *args, **kwargs):
            if doctype == 'Grouped Expense' and ptype == 'read':
                return False
            return native(doctype, ptype, *args, **kwargs)

        with patch('frappe.permissions.has_permission', side_effect=permission):
            with self.assertRaises(frappe.PermissionError):
                self.report()

    def test_invalid_dates_configuration_and_guest(self):
        with self.assertRaises(frappe.ValidationError):
            self.report(from_date=add_days(today(), 1))
        unconfigured = frappe.get_doc(dict(doctype='Mode of Payment',
            mode_of_payment='Statement unconfigured ' + self.fixture.key, type='Cash')).insert()
        with self.assertRaises(frappe.ValidationError):
            self.report(mode_of_payment=unconfigured.name)
        frappe.set_user('Guest')
        with self.assertRaises(frappe.PermissionError):
            self.report()

    def test_inaccessible_transfer_and_opening_voucher_reject_report(self):
        self.journal(100, add_days(today(), -1))
        self.fixture.transaction().insert().submit()
        native = frappe.permissions.has_permission
        for denied in ('Journal Entry', 'Treasury Transaction', 'Account'):
            def permission(doctype, ptype='read', *args, **kwargs):
                if doctype == denied and ptype == 'read':
                    return False
                return native(doctype, ptype, *args, **kwargs)

            with self.subTest(denied=denied), patch('frappe.permissions.has_permission', side_effect=permission):
                with self.assertRaises(frappe.PermissionError):
                    self.report()

    def test_workspace_patch_is_repeatable(self):
        from heavy_equipment_rental.patches.add_payment_statement_workspace import execute as upgrade

        frappe.db.set_default('her_payment_statement_workspace_v1', '')
        before = [(r.type, r.label, r.link_to) for r in frappe.get_doc('Workspace', 'Crane Operations').links
                  if r.link_to != 'Mode of Payment Statement']
        upgrade()
        upgrade()
        workspace = frappe.get_doc('Workspace', 'Crane Operations')
        self.assertEqual(sum(r.link_to == 'Mode of Payment Statement' for r in workspace.links), 1)
        self.assertEqual([(r.type, r.label, r.link_to) for r in workspace.links
                          if r.link_to != 'Mode of Payment Statement'], before)
