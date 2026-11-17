"""Populate the combined payroll grid on existing Timesheets without reposting."""

import frappe

from heavy_equipment_rental.driver_payroll import driver_work_summary


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
