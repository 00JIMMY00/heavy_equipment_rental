"""Post driver pay from a Crane Timesheet through Grouped Expense."""

from collections import defaultdict
from math import isfinite

import frappe
from frappe import _
from frappe.utils import flt, today

from heavy_equipment_rental.payment import payment_account


def validate_payroll_defaults(settings):
    companies = set()
    for row in settings.driver_payroll_defaults:
        if row.company in companies:
            frappe.throw(_("Set driver payroll defaults only once per Company."))
        companies.add(row.company)
        validate_payroll_default(row)


def validate_payroll_default(row):
    validate_payroll_expense_type(row)
    validate_payroll_mode(row.mode_of_payment, row.company)


def validate_payroll_expense_type(row):
    expense_type = frappe.db.get_value(
        "Expense Entry Type", row.expense_type, ["company", "enabled"], as_dict=True
    ) if row.expense_type else None
    if not expense_type or not expense_type.enabled or expense_type.company != row.company:
        frappe.throw(_("Select an enabled driver payroll Expense Entry Type for {0}.").format(row.company))


def validate_payroll_mode(mode, company):
    account = payment_account(mode, company)
    if frappe.db.get_value("Account", account, "disabled"):
        frappe.throw(_("Select a payroll Mode of Payment with an enabled account for {0}.").format(company))


def payroll_defaults(company):
    settings = frappe.get_cached_doc("Heavy Equipment Rental Settings")
    return next((row for row in settings.driver_payroll_defaults if row.company == company), None)


def driver_work_summary(sheet):
    hours_by_driver = defaultdict(float)
    overtime_by_driver = defaultdict(float)
    for row in sheet.timesheet_entries:
        if row.employee:
            overtime_by_driver[row.employee] += flt(row.overtime_hours)
            hours_by_driver[row.employee] += flt(row.worked_hours) + flt(row.overtime_hours)
    return {
        employee: {"unit": "Hour", "worked_hours": flt(hours, 6), "quantity": flt(hours, 6),
                   "overtime_hours": flt(overtime_by_driver[employee], 6)}
        for employee, hours in hours_by_driver.items()
    }


def sync_payroll_rows(sheet, company, summary):
    sheet.payroll_company = company
    work = {employee: values for employee, values in summary.items() if employee}
    previous = sheet.get_doc_before_save()
    if previous:
        paid = installment_totals(sheet.name, lock=True)
        if paid and (previous.crane != sheet.crane or previous.assignment != sheet.assignment
                     or paid.keys() - work.keys()):
            frappe.throw(_("Cancel the salary installment before changing its driver, crane or rental contract."))
    default = payroll_defaults(company) if work else None
    default_mode = default.mode_of_payment if default else None
    seen = set()
    for row in list(sheet.driver_payroll):
        if row.grouped_expense or row.expense_entry:
            frappe.throw(_("Driver payroll expense links are managed automatically."))
        rate = flt(row.rate)
        if not isfinite(rate) or rate < 0:
            frappe.throw(_("Driver payroll row {0}: Enter a finite, non-negative price per unit.").format(row.idx))
        overtime_price = flt(row.overtime_price)
        if not isfinite(overtime_price) or overtime_price < 0:
            frappe.throw(_("Driver payroll row {0}: Enter a finite, non-negative overtime price.").format(row.idx))
        amount = flt(row.amount)
        if not isfinite(amount) or amount < 0:
            frappe.throw(_("Driver payroll row {0}: Enter a finite, non-negative amount.").format(row.idx))
        if row.employee not in work:
            if amount or overtime_price or (rate and not row.fixed_amount):
                frappe.throw(_("Driver payroll row {0}: Clear the amount and price for the driver who is no longer on an operator shift.").format(row.idx))
            sheet.remove(row)
            continue
        if row.employee in seen:
            frappe.throw(_("Enter only one payroll amount per driver."))
        seen.add(row.employee)
        # Copies of historical payroll keep their earned amount as the starting
        # point until the user enters a new hourly rate.
        if row.unit in ("Day", "Month"):
            row.fixed_amount = 1
        row.update(work[row.employee])
        row.mode_of_payment = row.mode_of_payment or default_mode
        if row.fixed_amount or (amount and not rate and not overtime_price):
            row.fixed_amount = 1
            row.overtime_price = 0
            row.rate = implied_payroll_rate(row)
        else:
            regular_hours = row.worked_hours - row.overtime_hours
            calculated = rate * regular_hours + (overtime_price or rate) * row.overtime_hours
            if not isfinite(calculated):
                frappe.throw(_("Driver payroll row {0}: The calculated amount must be finite.").format(row.idx))
            row.amount = flt(calculated, row.precision("amount"))
        if row.amount and frappe.db.get_value("Employee", row.employee, "company") != company:
            frappe.throw(_("Driver {0} must belong to the Timesheet company to receive payroll.").format(row.employee))

    for employee, values in work.items():
        if employee not in seen:
            sheet.append("driver_payroll", {"employee": employee, "mode_of_payment": default_mode, **values})


def implied_payroll_rate(row):
    if not row.quantity or not row.amount:
        return None
    rate = row.amount / row.quantity
    if not isfinite(rate):
        frappe.throw(_("Driver payroll row {0}: The calculated price per unit must be finite.").format(row.idx))
    return flt(rate, row.precision("rate"))


def installment_totals(sheet_name, lock=False):
    totals = defaultdict(float)
    for employee, amount in frappe.db.sql(
        """select employee, total from `tabGrouped Expense`
           where crane_timesheet = %s and timesheet_salary_payment = 1 and docstatus = 1"""
        + (" for update" if lock else ""), sheet_name
    ):
        totals[employee] += flt(amount)
    return totals


@frappe.whitelist()
def get_salary_payments(timesheet):
    sheet = frappe.get_doc("Crane Timesheet", timesheet)
    sheet.check_permission("read")
    totals = installment_totals(sheet.name)
    for row in sheet.driver_payroll:
        if row.expense_entry:
            if frappe.db.get_value("Expense Entry", row.expense_entry, "docstatus") == 1:
                totals[row.employee] += flt(row.amount)
        elif row.grouped_expense:
            totals[row.employee] += flt(frappe.db.get_value("Grouped Expense",
                {"name": row.grouped_expense, "docstatus": 1}, "total"))
    return totals


def installment_context(sheet, employee):
    if sheet.docstatus == 2 or not any(row.employee == employee for row in sheet.driver_payroll):
        frappe.throw(_("Select a driver from a draft or submitted Timesheet."))
    default = payroll_defaults(sheet.payroll_company)
    if not default:
        frappe.throw(_("Set driver payroll defaults for {0} in Heavy Equipment Rental Settings.").format(sheet.payroll_company))
    validate_payroll_expense_type(default)
    return default.expense_type


@frappe.whitelist()
def make_salary_payment(timesheet, employee):
    frappe.has_permission("Grouped Expense", "create", throw=True)
    sheet = frappe.get_doc("Crane Timesheet", timesheet)
    sheet.check_permission("read")
    expense_type = installment_context(sheet, employee)
    return frappe.get_doc({
        "doctype": "Grouped Expense", "company": sheet.payroll_company, "employee": employee,
        "crane": sheet.crane, "crane_timesheet": sheet.name, "crane_assignment": sheet.assignment,
        "timesheet_salary_payment": 1,
        "mode_of_payment": next(row.mode_of_payment for row in sheet.driver_payroll if row.employee == employee),
        "items": [{"posting_date": today(), "expense_entry_type": expense_type}],
    })


def validate_installment(expense, sheet):
    expense_type = installment_context(sheet, expense.employee)
    if (sheet.crane != expense.crane or sheet.payroll_company != expense.company
            or any(row.expense_entry_type != expense_type for row in expense.items)):
        frappe.throw(_("Salary payments must use the Timesheet crane, company and payroll expense type."))


def cancel_driver_payroll(sheet):
    for row in sheet.driver_payroll:
        if row.grouped_expense:
            expense = frappe.get_doc("Grouped Expense", row.grouped_expense, for_update=True)
            if expense.docstatus == 1:
                expense.cancel()


def guard_payroll_cancel(expense):
    if expense.crane_timesheet and frappe.db.exists("Crane Driver Payroll", {
        "docstatus": 1,
        "parenttype": "Crane Timesheet",
        "parent": expense.crane_timesheet,
        ("grouped_expense" if expense.doctype == "Grouped Expense" else "expense_entry"): expense.name,
    }):
        frappe.throw(_("Cancel Crane Timesheet {0} to reverse its driver payroll.").format(expense.crane_timesheet))
