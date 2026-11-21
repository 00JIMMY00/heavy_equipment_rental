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
            date_of_joining=get_first_day(add_months(self.day, -1)), her_basic_salary=100, her_kpi_incentive=50,
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
        excess = self.expense(20, 11).insert()
        with self.assertRaisesRegex(frappe.ValidationError, r"only entitled to .*30"):
            excess.submit()
        self.assertEqual(excess.reload().docstatus, 0)
        self.assertFalse(excess.journal_entry)

        row = self.report_row()
        self.assertEqual((row["basic_salary"], row["kpi_incentive"]), (100, 50))
        self.assertEqual((row["basic_paid"], row["kpi_paid"], row["total_paid"]), (100, 20, 120))
        self.assertEqual((row["basic_due"], row["kpi_due"], row["total_due"]), (0, 30, 30))
        self.expense(30).insert().submit()
        self.assertEqual(self.report_row()["total_due"], 0)
        first_payment.cancel()
        self.assertEqual(self.report_row()["total_due"], 120)
        excess.submit()

    def test_grouped_and_normal_payments_share_the_limit(self):
        self.expense(100).insert().submit()
        excess = self.batch(25, 26).insert()
        with self.assertRaisesRegex(frappe.ValidationError, r"only entitled to .*50"):
            excess.submit()
        self.assertTrue(all(not row.journal_entry for row in excess.reload().items))
        batch = self.batch(25, 25).insert().submit()
        self.assertEqual(self.report_row()["total_paid"], 150)
        with self.assertRaisesRegex(frappe.ValidationError, r"only entitled to .*0"):
            self.expense(1).insert().submit()
        batch.cancel()
        self.assertEqual(self.report_row()["total_paid"], 100)

    def test_salary_requires_an_employee(self):
        with self.assertRaisesRegex(frappe.MandatoryError, r"Select an Employee"):
            self.expense(100, with_employee=False).insert().submit()
