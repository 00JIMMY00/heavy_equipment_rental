"""Monthly salary limits for employee payments posted through expenses."""

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import fmt_money, get_first_day, get_last_day, getdate


SALARY_FIELDS = ("her_basic_salary", "her_kpi_incentive")
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
    if not accounts or not employees:
        return {}

    params = {
        "company": company, "accounts": tuple(accounts), "employees": tuple(employees),
        "first": get_first_day(month), "last": get_last_day(month),
    }
    # A locking read sees the latest payments even if this transaction already read a snapshot.
    lock = " FOR UPDATE" if for_update else ""
    rows = frappe.db.sql(
        """
        SELECT expense.employee, line.amount
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
        SELECT expense.employee, line.debit
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
    total = defaultdict(Decimal)
    for employee, amount in rows + grouped_rows:
        total[employee] += money(amount)
    return dict(total)


def validate_salary_payment(company, employee, payments):
    accounts = set(salary_accounts(company))
    requested = defaultdict(Decimal)
    for posting_date, account, amount in payments:
        if account in accounts:
            requested[get_first_day(getdate(posting_date))] += money(amount)
    if not requested:
        return

    if not employee:
        frappe.throw(_("Select an Employee for a salary expense."), frappe.MandatoryError)

    # Serialize salary submissions for the same employee, including grouped payments.
    details = frappe.db.get_value("Employee", employee, ("company", *SALARY_FIELDS),
                                  as_dict=True, for_update=True)
    if not details or details.company != company:
        frappe.throw(_("The Employee must belong to the salary expense Company."))
    entitlement = sum(money(details[field]) for field in SALARY_FIELDS)
    for month, amount in sorted(requested.items()):
        paid = monthly_paid(company, accounts, [employee], month, for_update=True).get(employee, Decimal(0))
        remaining = max(entitlement - paid, Decimal(0))
        if amount > remaining:
            currency = frappe.get_cached_value("Company", company, "default_currency")
            frappe.throw(
                _("The employee is only entitled to {0} for {1}.").format(
                    fmt_money(remaining, currency=currency), month.strftime("%Y-%m"),
                ),
                title=_("Salary Entitlement Exceeded"),
            )
