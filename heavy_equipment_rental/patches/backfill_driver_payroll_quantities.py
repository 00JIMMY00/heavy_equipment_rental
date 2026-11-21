"""Populate the combined payroll grid on existing Timesheets without reposting."""

from calendar import monthrange
from collections import defaultdict
from datetime import time, timedelta

import frappe
from frappe.utils import flt, get_time, getdate


def driver_work_summary(sheet):
    units = {row.rental_rate_unit for row in sheet.timesheet_entries if row.rental_rate_unit}
    unit = sheet.rental_rate_unit or (units.pop() if len(units) == 1 else "Hour")
    hours_by_driver = defaultdict(float)
    days_by_driver = defaultdict(set)
    for row in sheet.timesheet_entries:
        if not row.employee:
            continue
        hours = flt(row.worked_hours) + flt(row.overtime_hours)
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


def execute():
    for name in frappe.get_all("Crane Timesheet", pluck="name"):
        sheet = frappe.get_doc("Crane Timesheet", name)
        if not sheet.payroll_company and sheet.assignment:
            company = frappe.get_cached_value("Rental Contract", sheet.assignment, "company")
            if company:
                sheet.db_set("payroll_company", company, update_modified=False)
        existing = {row.employee: row for row in sheet.driver_payroll}
        for employee, values in driver_work_summary(sheet).items():
            if not employee:
                continue
            if employee in existing:
                frappe.db.set_value("Crane Driver Payroll", existing[employee].name, values, update_modified=False)
            else:
                row = sheet.append("driver_payroll", {"employee": employee, **values})
                row.docstatus = sheet.docstatus
                row.db_insert()
