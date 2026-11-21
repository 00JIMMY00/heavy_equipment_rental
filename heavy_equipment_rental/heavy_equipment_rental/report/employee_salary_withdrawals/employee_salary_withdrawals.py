from calendar import monthrange
from collections import defaultdict
from datetime import time, timedelta

import frappe
from erpnext.accounts.utils import get_currency_precision
from frappe import _
from frappe.utils import flt, get_time, getdate

from heavy_equipment_rental.employee_salary import money, salary_accounts, salary_payment_rows


def period_amount(row, shifts, first, last, precision):
    if first <= row.period_start and row.period_end <= last:
        return row.amount

    # Allocate the stored payroll amount, including fixed amounts, by the
    # driver's recorded quantity. Cumulative rounding keeps adjacent periods additive.
    weights = defaultdict(float)
    for shift in shifts:
        hours = flt(shift.worked_hours) + flt(shift.overtime_hours)
        if hours <= 0:
            continue
        day = shift.work_date
        if row.unit not in ("Day", "Month"):
            weights[day] += hours
            continue
        days = [day]
        if shift.ends_next_day and shift.end_time and get_time(shift.end_time) > time.min:
            days.append(day + timedelta(days=1))
        for day in days:
            weights[day] = 1 / monthrange(day.year, day.month)[1] if row.unit == "Month" else 1

    total = sum(weights.values())
    if not total:
        return row.amount if first <= row.period_end <= last else 0
    before = sum(qty for day, qty in weights.items() if day < first)
    through = sum(qty for day, qty in weights.items() if day <= last)
    return flt(row.amount * through / total, precision) - flt(row.amount * before / total, precision)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not all(filters.get(key) for key in ("company", "employee", "from_date", "to_date")):
        frappe.throw(_("Select a company, employee and date range."))
    first, last = getdate(filters.from_date), getdate(filters.to_date)
    if first > last:
        frappe.throw(_("From Date must be before or equal to To Date."))
    company = frappe.get_doc("Company", filters.company)
    company.check_permission("read")
    employee = frappe.get_doc("Employee", filters.employee)
    employee.check_permission("read")
    if employee.company != company.name:
        frappe.throw(_("The Employee must belong to the selected Company."))

    payroll = frappe.db.sql("""
        SELECT sheet.name, sheet.period_start, sheet.period_end, sheet.docstatus, pay.amount, pay.unit
        FROM `tabCrane Timesheet` sheet
        JOIN `tabCrane Driver Payroll` pay ON pay.parent = sheet.name AND pay.parenttype = 'Crane Timesheet'
        WHERE sheet.payroll_company = %s AND pay.employee = %s AND sheet.docstatus IN (0, 1)
          AND sheet.period_start <= %s AND sheet.period_end >= %s AND pay.amount > 0
    """, (company.name, employee.name, last, first), as_dict=True)
    partial = [row.name for row in payroll if row.period_start < first or row.period_end > last]
    shifts = defaultdict(list)
    if partial:
        for shift in frappe.get_all("Timesheet Entry", filters={
            "parenttype": "Crane Timesheet", "parent": ["in", partial], "employee": employee.name,
        }, fields=["parent", "work_date", "worked_hours", "overtime_hours", "ends_next_day", "end_time"]):
            shifts[shift.parent].append(shift)
    precision = get_currency_precision()
    earned = [money(0), money(0)]
    for row in payroll:
        earned[row.docstatus] += money(flt(period_amount(row, shifts[row.name], first, last, precision), precision))
    linked = standalone = money(0)
    for _employee, sheet, value in salary_payment_rows(company.name, salary_accounts(company.name), [employee.name], first, last):
        if sheet:
            linked += money(value)
        else:
            standalone += money(value)

    fields = [
        ("draft_earned", "Draft Timesheet Salary"), ("posted_earned", "Submitted Timesheet Salary"),
        ("earned", "Total Timesheet Salary"), ("linked_paid", "Paid with Timesheet"),
        ("standalone_paid", "Paid without Timesheet"), ("paid", "Total Salary Withdrawals"),
        ("balance", "Salary Difference for Period"),
    ]
    columns = [dict(fieldname="employee", label=_("Employee"), fieldtype="Link", options="Employee", width=145)]
    columns.extend(dict(fieldname=key, label=_(label), fieldtype="Currency", options="currency", width=165)
                   for key, label in fields)
    due, paid = sum(earned), linked + standalone
    return columns, [dict(employee=employee.name, currency=company.default_currency, draft_earned=earned[0],
        posted_earned=earned[1], earned=due, linked_paid=linked, standalone_paid=standalone,
        paid=paid, balance=due-paid)], _("Timesheet salary follows work dates. Withdrawals follow the posting date of submitted salary expenses. A negative difference means withdrawals exceeded earnings in this period.")
