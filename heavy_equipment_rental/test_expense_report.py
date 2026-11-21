from heavy_equipment_rental.test_expenses import legacy_expense
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days

from heavy_equipment_rental.heavy_equipment_rental.report.crane_expense_report.crane_expense_report import execute


class TestExpenseReport(FrappeTestCase):
    def setUp(self):
        from heavy_equipment_rental.test_expenses import enable_historical_fixtures
        enable_historical_fixtures(self)
        from heavy_equipment_rental.test_consolidated_expenses import TestGroupedExpenses
        self.fixture = TestGroupedExpenses()
        self.fixture.setUp()
        self.batch = self.fixture.batch().insert()
        self.batch.submit()
        self.normal = legacy_expense(self.batch, self.batch.items[0])
        self.normal.description = 'Standalone report expense'
        self.normal.set('expenses', [dict(expense_entry_type=self.fixture.default.expense_type, amount=20),
            dict(expense_entry_type=self.fixture.default.expense_type, amount=30)])
        self.normal.insert().submit()
        from heavy_equipment_rental.patches.unify_grouped_expenses import execute as migrate
        migrate()
        migrate()
        self.normal = frappe.get_doc('Grouped Expense', {'legacy_expense': self.normal.name})
        self.filters = dict(company=self.batch.company, crane=self.batch.crane,
            from_date=today(), to_date=add_days(today(), 1), group_by='None', show_details=1)

    def report(self, **overrides):
        return execute(dict(self.filters, **overrides))

    def test_details_chart_and_summary_reconcile_to_posted_journals(self):
        columns, rows, _, chart, summary, skip_total = self.report()
        total = rows.pop()
        self.assertEqual(total['is_total_row'], 1)
        self.assertEqual(total['indent'], 0)
        self.assertEqual(total['amount'], 250)
        self.assertEqual(sum(row['amount'] for row in rows), 250)
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(chart['data']['datasets'][0]['values']), 250)
        self.assertEqual(summary[0]['value'], 250)
        self.assertEqual(len(summary), 1)
        self.assertEqual([column['fieldname'] for column in columns], [
            'posting_date', 'crane_name', 'amount', 'description', 'timesheet', 'expense_type_title', 'source',
            'mode_of_payment', 'cost_center', 'employee',
        ])
        self.assertTrue(skip_total)
        self.assertEqual(sum(frappe.db.get_value('Journal Entry', name, 'total_debit') for name in {r['journal_entry'] for r in rows}), 250)
        self.assertTrue(all(row['timesheet'] == self.fixture.sheet.name for row in rows))
        self.assertEqual({r['source_type'] for r in rows}, {'Grouped Expense'})

    def test_grouping_filters_and_cancelled_sources(self):
        for group in ('Crane', 'Timesheet', 'Expense Type', 'Mode of Payment', 'Month'):
            rows = self.report(group_by=group)[1]
            self.assertEqual(rows.pop()['amount'], 250)
            self.assertEqual(sum(r['amount'] for r in rows if r['is_group']), 250)
            self.assertEqual(sum(r['amount'] for r in rows if not r['is_group']), 250)
            rows = self.report(group_by=group, show_details=0)[1]
            self.assertTrue(rows.pop()['is_total_row'])
            self.assertTrue(all(r['is_group'] for r in rows))
        omitted = dict(self.filters, group_by='Crane')
        omitted.pop('show_details')
        self.assertTrue(all(r['is_group'] for r in execute(omitted)[1][:-1]))
        self.assertEqual(self.report(source='Grouped Expense')[4][0]['value'], 250)
        self.assertEqual(self.report(source='Expense Entry')[4][0]['value'], 50)
        self.assertEqual(self.report(to_date=today())[4][0]['value'], 175)
        self.assertEqual(self.report(timesheet=self.fixture.sheet.name)[4][0]['value'], 250)
        self.assertEqual(self.report(expense_type=self.fixture.default.expense_type, mode_of_payment=self.fixture.mode)[4][0]['value'], 250)
        self.batch.cancel()
        self.assertEqual(self.report()[4][0]['value'], 50)
        self.normal.cancel()
        self.assertFalse(self.report()[1])
        self.assertEqual(self.report()[4][0]['value'], 0)

    def test_combined_filters_match_the_expense_row_and_its_group(self):
        company = self.batch.company
        center = frappe.get_doc(dict(doctype='Cost Center', company=company,
            cost_center_name='Expense report ' + frappe.generate_hash(length=8),
            parent_cost_center=frappe.db.get_value('Cost Center', self.batch.cost_center, 'parent_cost_center'))).insert()
        expense_type = frappe.get_doc(dict(doctype='Expense Entry Type', company=company,
            title='Report override ' + frappe.generate_hash(length=8),
            account=frappe.db.get_value('Expense Entry Type', self.fixture.default.expense_type, 'account'))).insert()
        mode = frappe.get_doc(dict(doctype='Mode of Payment', mode_of_payment='Report ' + frappe.generate_hash(length=8),
            type='Cash', accounts=[dict(company=company, default_account=frappe.db.get_value('Mode of Payment Account',
                {'company': company, 'parent': self.fixture.mode}, 'default_account'))])).insert()
        batch = self.fixture.batch()
        batch.cost_center = center.name
        batch.items[1].expense_entry_type = expense_type.name
        batch.items[1].mode_of_payment = mode.name
        batch.insert().submit()

        filters = dict(cost_center=center.name, employee=self.fixture.employee, timesheet=self.fixture.sheet.name,
            expense_type=expense_type.name, mode_of_payment=mode.name, grouped_expense=batch.name)
        _, rows, _, _, summary, _ = self.report(**filters)
        self.assertEqual(rows.pop()['amount'], 75)
        self.assertEqual(len(rows), 1)
        self.assertEqual(summary[0]['value'], 75)
        row = rows[0]
        self.assertEqual(row['posting_date'], add_days(today(), 1))
        self.assertEqual(row['source'], batch.name)
        self.assertEqual(row['cost_center'], center.name)
        self.assertEqual(row['mode_of_payment'], mode.name)
        self.assertEqual(row['employee'], self.fixture.employee)
        self.assertFalse(self.report(**dict(filters, cost_center=self.batch.cost_center))[1])
        self.assertFalse(self.report(**dict(filters, grouped_expense=self.batch.name))[1])
        self.assertFalse(self.report(**dict(filters, mode_of_payment=self.fixture.mode))[1])
        self.assertEqual(self.report(cost_center=self.batch.cost_center)[4][0]['value'], 250)

    def test_legacy_group_is_counted_once_and_keeps_group_identity(self):
        batch = self.fixture.batch().insert()
        for row in batch.items:
            expense = legacy_expense(batch, row).insert()
            expense.submit()
            row.db_set('expense_entry', expense.name)
            row.db_set('docstatus', 1)
        batch.db_set('docstatus', 1)
        rows = self.report()[1]
        self.assertEqual(rows.pop()['amount'], 450)
        self.assertEqual(sum(r['amount'] for r in rows), 450)
        self.assertEqual(sum(r['amount'] for r in rows if r['source'] == batch.name), 200)
        self.assertEqual(self.report(source='Grouped Expense')[4][0]['value'], 450)
        self.assertEqual(self.report(source='Expense Entry')[4][0]['value'], 50)

    def test_permission_and_invalid_dates(self):
        with self.assertRaises(frappe.ValidationError):
            self.report(from_date=add_days(today(), 2))
        frappe.set_user('Guest')
        try:
            with self.assertRaises(frappe.PermissionError):
                self.report()
        finally:
            frappe.set_user('Administrator')
