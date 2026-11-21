"""Employee salary payments posted through expenses."""

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day


SALARY_ACCOUNT_NAMES = ("Salary", "Salaries", "Salaries and Wages", "الرواتب", "رواتب", "الأجور والرواتب")


def salary_accounts(company):
    return frappe.get_all(
        "Account",
        filters={"company": company, "root_type": "Expense", "is_group": 0},
        or_filters={"account_name": ["in", SALARY_ACCOUNT_NAMES], "her_is_salary_account": 1},
        pluck="name",
    )


def money(value):
    return Decimal(str(value or 0))


def monthly_paid(company, accounts, employees, month, *, for_update=False):
    totals = defaultdict(Decimal)
    for employee, sheet, amount in salary_payment_rows(
        company, accounts, employees, get_first_day(month), get_last_day(month), for_update=for_update
    ):
        totals[employee] += money(amount)
    return dict(totals)


def salary_payment_rows(company, accounts, employees, first=None, last=None, *, for_update=False):
    if not accounts or not employees:
        return []

    params = {
        "company": company, "accounts": tuple(accounts), "employees": tuple(employees),
        "first": first, "last": last,
    }
    # A locking read sees the latest payments even if this transaction already read a snapshot.
    lock = " FOR UPDATE" if for_update else ""
    expense_dates = journal_dates = ""
    if first is not None or last is not None:
        expense_dates = " AND expense.posting_date BETWEEN %(first)s AND %(last)s"
        journal_dates = " AND journal.posting_date BETWEEN %(first)s AND %(last)s"
    rows = frappe.db.sql(
        """
        SELECT expense.employee, expense.crane_timesheet, line.amount
        FROM `tabExpense Entry` AS expense
        INNER JOIN `tabExpense Entry Detail` AS line
            ON line.parent = expense.name AND line.parenttype = 'Expense Entry'
        WHERE expense.company = %(company)s AND expense.docstatus = 1
            AND expense.employee IN %(employees)s
            AND line.expense_entry_account IN %(accounts)s
        """ + expense_dates + lock,
        params,
    )
    grouped_rows = frappe.db.sql(
        """
        SELECT expense.employee, expense.crane_timesheet, line.debit
        FROM `tabGrouped Expense` AS expense
        INNER JOIN `tabGrouped Expense Item` AS item
            ON item.parent = expense.name AND item.parenttype = 'Grouped Expense'
        INNER JOIN `tabJournal Entry` AS journal
            ON journal.name = item.journal_entry AND journal.docstatus = 1
        INNER JOIN `tabJournal Entry Account` AS line
            ON line.parent = journal.name AND line.parenttype = 'Journal Entry'
        WHERE expense.company = %(company)s AND expense.docstatus = 1
            AND expense.employee IN %(employees)s
            AND (item.expense_entry IS NULL OR item.expense_entry = '')
            AND line.account IN %(accounts)s AND line.debit > 0
        """ + journal_dates + lock,
        params,
    )
    # Legacy grouped rows post through Expense Entry and are already counted there.
    return rows + grouped_rows


def validate_salary_payment(company, employee, payments):
    accounts = set(salary_accounts(company))
    if not any(account in accounts for _date, account, _amount in payments):
        return
    if not employee:
        frappe.throw(_("Select an Employee for a salary expense."), frappe.MandatoryError)
    if frappe.db.get_value("Employee", employee, "company") != company:
        frappe.throw(_("The Employee must belong to the salary expense Company."))


@frappe.whitelist()
def driver_salary_balances(employees: list[str] | str, company: str | None = None):
    from frappe.desk.query_report import get_report_doc

    get_report_doc("Employee Salary Withdrawals")
    frappe.has_permission("Crane Timesheet", "read", throw=True)
    employees = frappe.parse_json(employees)
    if not isinstance(employees, list) or not all(isinstance(name, str) for name in employees):
        frappe.throw(_("Select valid employees."))
    if not employees:
        return []

    drivers = frappe.get_list("Employee", filters={"name": ["in", employees]},
                              fields=["name", "employee_name", "company"], limit_page_length=0)
    by_company = defaultdict(list)
    for driver in drivers:
        if not company or driver.company == company:
            by_company[driver.company].append(driver)

    balances = []
    for payroll_company, drivers in by_company.items():
        company_doc = frappe.get_doc("Company", payroll_company)
        company_doc.check_permission("read")
        ids = tuple(driver.name for driver in drivers)
        earned = defaultdict(Decimal)
        submitted = set()
        for employee, sheet, amount in frappe.db.sql("""
            SELECT pay.employee, sheet.name, pay.amount
            FROM `tabCrane Timesheet` sheet
            JOIN `tabCrane Driver Payroll` pay
              ON pay.parent = sheet.name AND pay.parenttype = 'Crane Timesheet'
            WHERE sheet.docstatus = 1 AND sheet.payroll_company = %s AND pay.employee IN %s
        """, (payroll_company, ids)):
            earned[employee] += money(amount)
            submitted.add((employee, sheet))

        linked = defaultdict(Decimal)
        paid = defaultdict(Decimal)
        for employee, sheet, amount in salary_payment_rows(payroll_company, salary_accounts(payroll_company), ids):
            paid[employee] += money(amount)
            if (employee, sheet) in submitted:
                linked[employee] += money(amount)
        for driver in drivers:
            balances.append(dict(employee=driver.name, driver=driver.employee_name or driver.name,
                                 currency=company_doc.default_currency, remaining=earned[driver.name] - linked[driver.name],
                                 difference=earned[driver.name] - paid[driver.name]))
    return balances
