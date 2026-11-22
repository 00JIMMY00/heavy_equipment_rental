from calendar import monthrange
from collections import defaultdict
from datetime import time, timedelta
from decimal import Decimal

import frappe
from erpnext.accounts.utils import get_currency_precision
from frappe import _
from frappe.utils import cint, flt, get_time, getdate

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
    return salary_report(filters)


def salary_report(filters, detail=None):
    filters = frappe._dict(filters or {})
    if not all(filters.get(key) for key in ("company", "from_date", "to_date")):
        frappe.throw(_("Select a company and date range."))
    first, last = getdate(filters.from_date), getdate(filters.to_date)
    if first > last:
        frappe.throw(_("From Date must be before or equal to To Date."))
    company = frappe.get_doc("Company", filters.company)
    company.check_permission("read")
    employee_filters = {"company": company.name}
    if filters.employee:
        employee = frappe.get_doc("Employee", filters.employee)
        employee.check_permission("read")
        if employee.company != company.name:
            frappe.throw(_("The Employee must belong to the selected Company."))
        employee_filters["name"] = employee.name
    employees = frappe.get_list("Employee", filters=employee_filters, fields=["name", "employee_name"],
                                order_by="employee_name, name", limit_page_length=0)
    show_drafts = cint(filters.show_drafts)
    fields = [("posted_earned", "Earned Salary")]
    if show_drafts:
        fields.extend([("draft_earned", "Draft Timesheet Salary"), ("earned", "Total Timesheet Salary")])
    fields.extend([("paid", "Withdrawals"), ("balance", "Salary Difference")])
    columns = [
        dict(fieldname="employee_name", label=_("Employee Name"), fieldtype="Data", width=188, sticky=True),
    ]
    columns.extend(dict(fieldname=key, label=_(label), fieldtype="Currency", options="currency", width=155)
                   for key, label in fields)
    if frappe.has_permission("Grouped Expense", "create"):
        columns.append(dict(fieldname="payment", label=_("Payment"), fieldtype="Data", width=180))
    ids = tuple(employee.name for employee in employees)
    if not ids:
        if detail:
            frappe.throw(_("You do not have access to this employee."), frappe.PermissionError)
        return columns, []

    payroll = frappe.db.sql("""
        SELECT sheet.name, pay.employee, sheet.period_start, sheet.period_end, sheet.docstatus, pay.amount, pay.unit
        FROM `tabCrane Timesheet` sheet
        JOIN `tabCrane Driver Payroll` pay ON pay.parent = sheet.name AND pay.parenttype = 'Crane Timesheet'
        WHERE sheet.payroll_company = %s AND pay.employee IN %s AND sheet.docstatus IN %s
          AND sheet.period_start <= %s AND sheet.period_end >= %s AND pay.amount > 0
    """, (company.name, ids, (0, 1) if show_drafts else (1,), last, first), as_dict=True)
    partial = {row.name for row in payroll if row.period_start < first or row.period_end > last}
    shifts = defaultdict(list)
    if partial:
        for shift in frappe.get_all("Timesheet Entry", filters={
            "parenttype": "Crane Timesheet", "parent": ["in", list(partial)], "employee": ["in", ids],
        }, fields=["parent", "employee", "work_date", "worked_hours", "overtime_hours", "ends_next_day", "end_time"]):
            shifts[shift.parent, shift.employee].append(shift)
    precision = get_currency_precision()
    earnings = defaultdict(Decimal)
    earning_sources = []
    withdrawal_sources = defaultdict(Decimal)
    for row in payroll:
        amount = period_amount(row, shifts[row.name, row.employee], first, last, precision)
        amount = money(flt(amount, precision))
        earnings[row.employee, row.docstatus] += amount
        if (
            detail in ("earned", "draft", "total_earned", "balance") and amount
            and (detail not in ("earned", "draft") or row.docstatus == int(detail == "earned"))
        ):
            earning_sources.append(dict(doctype="Crane Timesheet", name=row.name, amount=amount,
                from_date=max(first, row.period_start), to_date=min(last, row.period_end), docstatus=row.docstatus))
    withdrawals = defaultdict(Decimal)
    payments = salary_payment_rows(company.name, salary_accounts(company.name), ids, first, last,
                                   with_sources=detail in ("paid", "balance"))
    for employee, sheet, amount, *source in payments:
        withdrawals[employee, bool(sheet)] += money(amount)
        if source:
            name, date, doctype = source
            withdrawal_sources[doctype, name, date, bool(sheet)] += money(amount)

    rows = []
    for employee in employees:
        name = employee.name
        posted = earnings[name, 1]
        linked, standalone = withdrawals[name, True], withdrawals[name, False]
        paid = linked + standalone
        row = dict(employee=name, employee_name=employee.employee_name, currency=company.default_currency,
                   posted_earned=posted, linked_paid=linked, standalone_paid=standalone, paid=paid, balance=posted - paid)
        if show_drafts:
            row.update(draft_earned=earnings[name, 0], earned=posted + earnings[name, 0])
        rows.append(row)
    if detail:
        sources = [dict(doctype=doctype, name=name, date=date, linked=linked, amount=amount)
                   for (doctype, name, date, linked), amount in withdrawal_sources.items()]
        return dict(employee=rows[0],
                    earnings=readable_sources(earning_sources, "from_date"),
                    withdrawals=readable_sources(sources, "date"))

    balance_status = filters.get("balance_status")
    if balance_status == "Owed":
        rows = [row for row in rows if row["balance"] > 0]
    elif balance_status == "Extra":
        rows = [row for row in rows if row["balance"] < 0]
    elif balance_status == "Settled":
        rows = [row for row in rows if row["balance"] == 0 and (row["posted_earned"] or row["paid"])]
    covered = float(sum(min(row["posted_earned"], row["paid"]) for row in rows))
    owed = float(sum(max(row["balance"], 0) for row in rows))
    above_earnings = float(sum(max(-row["balance"], 0) for row in rows))
    covered_label = _("Salary Paid")
    owed_label = _("Still Owed")
    excess_label = _("Extra Withdrawals")
    covered_color, owed_color, excess_color = "#18794E", "#74B88B", "#BF4045"

    chart = dict(
        type="bar", barOptions=dict(stacked=True), showLegend=0,
        colors=[covered_color, owed_color, excess_color],
        data=dict(labels=[_("Earned Salary"), _("Salary Withdrawals")], datasets=[
            dict(name=covered_label, values=[covered, covered]),
            dict(name=owed_label, values=[owed, 0]),
            dict(name=excess_label, values=[0, above_earnings]),
        ]),
        currency=company.default_currency, precision=precision,
        legend_help={
            covered_label: _("Salary already withdrawn, up to what each employee earned in the selected period."),
            owed_label: _("Salary employees earned but have yet to withdraw in the selected period."),
            excess_label: _("Money employees withdrew beyond what they earned in the selected period."),
        },
        withdrawal_breakdown=dict(
            type="donut", showLegend=0, colors=[covered_color, excess_color],
            data=dict(labels=[covered_label, excess_label], datasets=[dict(values=[covered, above_earnings])]),
        ),
    )
    net = sum(row["balance"] for row in rows)
    summary = [
        dict(label=_("Still Owed"), value=owed, indicator="Green", datatype="Currency", currency=company.default_currency),
        dict(label=_("Extra Withdrawals"), value=above_earnings, indicator="Red", datatype="Currency",
             currency=company.default_currency),
        dict(label=_("Net Balance"), value=net, indicator="Red" if net < 0 else "Green", datatype="Currency",
             currency=company.default_currency),
    ]
    return (columns, rows,
            _("Salary Difference uses submitted Timesheet earnings by work date less submitted salary withdrawals by posting date."),
            chart, summary)


def readable_sources(rows, sort_date):
    visible = []
    restricted = False
    permissions = {}
    for row in sorted(rows, key=lambda row: (row[sort_date], row["name"])):
        key = row["doctype"], row["name"]
        if key not in permissions:
            permissions[key] = frappe.has_permission(key[0], "read", doc=key[1])
        if permissions[key]:
            visible.append(row)
        else:
            restricted = True
    return dict(rows=visible, restricted=restricted)


@frappe.whitelist()
def get_salary_details(company, employee, from_date, to_date, detail, show_drafts=0):
    from frappe.desk.query_report import get_report_doc

    get_report_doc("Employee Salary Withdrawals")
    if not employee or detail not in ("earned", "draft", "total_earned", "paid", "balance"):
        frappe.throw(_("Select an employee and a salary amount."))
    return salary_report(dict(company=company, employee=employee, from_date=from_date, to_date=to_date,
                              show_drafts=detail in ("draft", "total_earned") and cint(show_drafts)),
                         detail=detail)


@frappe.whitelist()
def prepare_salary_payment(company, employee):
    from frappe.desk.query_report import get_report_doc
    from heavy_equipment_rental.driver_payroll import salary_payment_draft

    get_report_doc("Employee Salary Withdrawals")
    frappe.has_permission("Grouped Expense", "create", throw=True)
    frappe.get_doc("Company", company).check_permission("read")
    driver = frappe.get_doc("Employee", employee)
    driver.check_permission("read")
    if driver.company != company:
        frappe.throw(_("The Employee must belong to the selected Company."))

    return salary_payment_draft(company, employee)
