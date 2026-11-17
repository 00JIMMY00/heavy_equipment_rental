"""Post driver pay from a Crane Timesheet through HER Expense Entries."""

from calendar import monthrange
from collections import defaultdict
from datetime import time, timedelta
from math import isfinite

import frappe
from frappe import _
from frappe.utils import flt, get_time, getdate, today

from heavy_equipment_rental.payment import payment_account


def validate_payroll_defaults(settings):
    companies = set()
    for row in settings.driver_payroll_defaults:
        if row.company in companies:
            frappe.throw(_("Set driver payroll defaults only once per Company."))
        companies.add(row.company)
        validate_payroll_default(row)


def validate_payroll_default(row):
    expense_type = frappe.db.get_value(
        "Expense Entry Type", row.expense_type, ["company", "enabled"], as_dict=True
    ) if row.expense_type else None
    if not expense_type or not expense_type.enabled or expense_type.company != row.company:
        frappe.throw(_("Select an enabled driver payroll Expense Entry Type for {0}.").format(row.company))
    account = payment_account(row.mode_of_payment, row.company)
    if frappe.db.get_value("Account", account, "disabled"):
        frappe.throw(_("Select a payroll Mode of Payment with an enabled account for {0}.").format(row.company))


def driver_work_summary(sheet):
    units = {row.rental_rate_unit for row in sheet.timesheet_entries if row.rental_rate_unit}
    unit = sheet.rental_rate_unit or (units.pop() if len(units) == 1 else "Hour")
    hours_by_driver = defaultdict(float)
    days_by_driver = defaultdict(set)
    for row in sheet.timesheet_entries:
        hours = flt(row.worked_hours)
        hours_by_driver[row.employee] += hours
        if unit in ("Day", "Month") and hours > 0 and row.work_date:
            day = getdate(row.work_date)
            days_by_driver[row.employee].add(day)
            if row.ends_next_day and row.end_time and get_time(row.end_time) > time.min:
                days_by_driver[row.employee].add(day + timedelta(days=1))

    summary = {}
    for employee, hours in hours_by_driver.items():
        days = days_by_driver[employee]
        quantity = hours
        if unit == "Day":
            quantity = len(days)
        elif unit == "Month":
            quantity = sum(1 / monthrange(day.year, day.month)[1] for day in sorted(days))
        summary[employee] = {"unit": unit, "worked_hours": flt(hours, 6), "quantity": flt(quantity, 9)}
    return summary


def sync_payroll_rows(sheet, company, summary):
    sheet.payroll_company = company
    work = {employee: values for employee, values in summary.items() if employee}
    seen = set()
    for row in list(sheet.driver_payroll):
        if row.expense_entry:
            frappe.throw(_("Driver payroll Expense Entry links are managed automatically."))
        rate = flt(row.rate)
        if not isfinite(rate) or rate < 0:
            frappe.throw(_("Driver payroll row {0}: Enter a finite, non-negative price per unit.").format(row.idx))
        amount = flt(row.amount)
        if not isfinite(amount) or amount < 0:
            frappe.throw(_("Driver payroll row {0}: Enter a finite, non-negative amount.").format(row.idx))
        if row.employee not in work:
            if amount or (rate and not row.fixed_amount):
                frappe.throw(_("Driver payroll row {0}: Clear the amount and price for the driver who is no longer on an operator shift.").format(row.idx))
            sheet.remove(row)
            continue
        if row.employee in seen:
            frappe.throw(_("Enter only one payroll amount per driver."))
        seen.add(row.employee)
        row.update(work[row.employee])
        if row.fixed_amount or (amount and not rate):
            row.fixed_amount = 1
            row.rate = implied_payroll_rate(row)
        elif rate:
            calculated = rate * row.quantity
            if not isfinite(calculated):
                frappe.throw(_("Driver payroll row {0}: The calculated amount must be finite.").format(row.idx))
            row.amount = flt(calculated, row.precision("amount"))
        if row.amount and frappe.db.get_value("Employee", row.employee, "company") != company:
            frappe.throw(_("Driver {0} must belong to the Timesheet company to receive payroll.").format(row.employee))

    for employee, values in work.items():
        if employee not in seen:
            sheet.append("driver_payroll", {"employee": employee, **values})


def implied_payroll_rate(row):
    if not row.quantity or not row.amount:
        return None
    rate = row.amount / row.quantity
    if not isfinite(rate):
        frappe.throw(_("Driver payroll row {0}: The calculated price per unit must be finite.").format(row.idx))
    return flt(rate, row.precision("rate"))


def post_driver_payroll(sheet):
    rows = [row for row in sheet.driver_payroll if row.amount and not row.expense_entry]
    if not rows:
        return
    settings = frappe.get_single("Heavy Equipment Rental Settings")
    default = next((row for row in settings.driver_payroll_defaults if row.company == sheet.payroll_company), None)
    if not default:
        frappe.throw(_("Set driver payroll defaults for {0} in Heavy Equipment Rental Settings.").format(sheet.payroll_company))
    validate_payroll_default(default)

    posting_date = today()
    for row in rows:
        expense = frappe.get_doc({
            "doctype": "Expense Entry",
            "company": sheet.payroll_company,
            "posting_date": posting_date,
            "mode_of_payment": default.mode_of_payment,
            "description": _("Driver payroll for Crane Timesheet {0}").format(sheet.name),
            "employee": row.employee,
            "crane": sheet.crane,
            "crane_assignment": sheet.assignment,
            "crane_timesheet": sheet.name,
            "expenses": [{"expense_entry_type": default.expense_type, "amount": row.amount}],
        })
        expense.insert()
        expense.submit()
        row.db_set("expense_entry", expense.name, update_modified=False)


def cancel_driver_payroll(sheet):
    for row in sheet.driver_payroll:
        if row.expense_entry:
            expense = frappe.get_doc("Expense Entry", row.expense_entry, for_update=True)
            if expense.docstatus == 1:
                expense.cancel()


def guard_payroll_cancel(expense):
    if expense.crane_timesheet and frappe.db.exists("Crane Driver Payroll", {
        "docstatus": 1,
        "parenttype": "Crane Timesheet",
        "parent": expense.crane_timesheet,
        "expense_entry": expense.name,
    }):
        frappe.throw(_("Cancel Crane Timesheet {0} to reverse its driver payroll.").format(expense.crane_timesheet))
