import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, get_first_day, today

from heavy_equipment_rental.employee_salary import salary_accounts
from heavy_equipment_rental.heavy_equipment_rental.report.monthly_salary_report.monthly_salary_report import (
    execute,
)


class TestEmployeeSalary(FrappeTestCase):
    def setUp(self):
        from heavy_equipment_rental.test_expenses import enable_historical_fixtures
        enable_historical_fixtures(self)
        self.company = frappe.db.get_value("Company", {}, "name")
        self.mode = frappe.db.get_value("Mode of Payment Account", {"company": self.company}, "parent")
        self.expense_type = frappe.db.get_value("Expense Entry Type", {
            "company": self.company, "enabled": 1, "account": ["not in", salary_accounts(self.company)],
        }, ["name", "account"], as_dict=True)
        self.day = today()
        key = frappe.generate_hash(length=8)
        account = frappe.get_doc(dict(
            doctype="Account", company=self.company, account_name=f"Payroll {key}", her_is_salary_account=1,
            parent_account=frappe.db.get_value("Account", self.expense_type.account, "parent_account"),
        )).insert()
        self.salary_type = frappe.get_doc(dict(
            doctype="Expense Entry Type", title=f"Payroll {key}", company=self.company,
            account=account.name,
        )).insert()
        self.employee = frappe.get_doc(dict(
            doctype="Employee", first_name=f"Payroll {key}", company=self.company, gender="Male",
            date_of_joining=get_first_day(add_months(self.day, -1)),
        )).insert().name

    def expense(self, *amounts, day=None, with_employee=True):
        return frappe.get_doc(dict(
            doctype="Expense Entry", company=self.company, mode_of_payment=self.mode,
            employee=self.employee if with_employee else None, posting_date=day or self.day,
            description="Monthly salary test",
            expenses=[dict(expense_entry_type=self.salary_type.name, amount=amount) for amount in amounts],
        ))

    def batch(self, *amounts):
        return frappe.get_doc(dict(
            doctype="Grouped Expense", company=self.company, mode_of_payment=self.mode, employee=self.employee,
            items=[dict(posting_date=self.day, description="Salary instalment", amount=amount,
                        expense_entry_type=self.salary_type.name) for amount in amounts],
        ))

    def report_row(self):
        _, rows, _ = execute(dict(company=self.company, month=self.day))
        return next(row for row in rows if row["employee"] == self.employee)

    def test_payments_count_salary_lines_in_the_posting_month_and_cancellation_restores_balance(self):
        _, year_start, _ = get_fiscal_year(self.day, company=self.company)
        other_month = get_first_day(add_months(self.day, -1))
        if other_month < year_start:
            other_month = get_first_day(add_months(self.day, 1))
        self.expense(150, day=other_month).insert().submit()
        first_payment = self.expense(90, 30)
        first_payment.append("expenses", dict(expense_entry_type=self.expense_type.name, amount=100))
        first_payment.insert().submit()
        self.assertEqual(self.report_row()["total_paid"], 120)
        self.batch(80).insert().submit()
        self.assertEqual(self.report_row()["total_paid"], 200)
        first_payment.cancel()
        self.assertEqual(self.report_row()["total_paid"], 80)

    def test_withdrawals_include_standalone_salary_only_in_selected_period(self):
        from heavy_equipment_rental.heavy_equipment_rental.report.employee_salary_withdrawals.employee_salary_withdrawals import execute as withdrawals

        batch = self.batch(30)
        batch.append("items", dict(posting_date=self.day, description="Other expense", amount=7,
                                  expense_entry_type=self.expense_type.name))
        batch.insert().submit()
        self.expense(20).insert().submit()
        self.batch(10).insert()
        filters = dict(company=self.company, employee=self.employee, from_date=self.day, to_date=self.day)
        row = withdrawals(filters)[1][0]
        self.assertEqual((row["linked_paid"], row["standalone_paid"], row["paid"], row["balance"]), (0, 50, 50, -50))
        all_filters = {key: value for key, value in filters.items() if key != "employee"}
        columns, employees, _, chart = withdrawals(all_filters)
        self.assertNotIn("draft_earned", [column["fieldname"] for column in columns])
        self.assertIn(row, employees)
        self.assertTrue(chart["barOptions"]["stacked"])
        self.assertEqual([sum(totals) for totals in zip(*(d["values"] for d in chart["data"]["datasets"]))],
                         [float(sum(r[field] for r in employees)) for field in ("posted_earned", "paid")])
        donut = chart["withdrawal_breakdown"]["data"]["datasets"][0]["values"]
        self.assertEqual(donut[1], float(sum(max(-r["balance"], 0) for r in employees)))
        columns, rows, _, _ = withdrawals(dict(filters, show_drafts=1))
        self.assertIn("draft_earned", [column["fieldname"] for column in columns])
        self.assertEqual(rows[0]["balance"], row["balance"])
        batch.cancel()
        self.assertEqual(withdrawals(filters)[1][0]["paid"], 20)
        other_day = add_months(self.day, -1)
        self.assertEqual(withdrawals(dict(filters, from_date=other_day, to_date=other_day))[1][0]["paid"], 0)

    def test_salary_requires_an_employee(self):
        with self.assertRaisesRegex(frappe.MandatoryError, r"Select an Employee"):
            self.expense(100, with_employee=False).insert().submit()
