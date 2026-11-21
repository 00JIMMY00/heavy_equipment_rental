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


def salary_payment_rows(company, accounts, employees, first, last, *, for_update=False):
    if not accounts or not employees:
        return []

    params = {
        "company": company, "accounts": tuple(accounts), "employees": tuple(employees),
        "first": first, "last": last,
    }
    # A locking read sees the latest payments even if this transaction already read a snapshot.
    lock = " FOR UPDATE" if for_update else ""
    rows = frappe.db.sql(
        """
        SELECT expense.employee, expense.crane_timesheet, line.amount
        FROM `tabExpense Entry` AS expense
        INNER JOIN `tabExpense Entry Detail` AS line
            ON line.parent = expense.name AND line.parenttype = 'Expense Entry'
        WHERE expense.company = %(company)s AND expense.docstatus = 1
            AND expense.employee IN %(employees)s
            AND expense.posting_date BETWEEN %(first)s AND %(last)s
            AND line.expense_entry_account IN %(accounts)s
        """ + lock,
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
            AND journal.posting_date BETWEEN %(first)s AND %(last)s
            AND line.account IN %(accounts)s AND line.debit > 0
        """ + lock,
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
