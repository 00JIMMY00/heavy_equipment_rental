"""Populate the overtime breakdown from saved shifts without repricing payroll."""

import frappe


def execute():
    frappe.db.sql("""
        UPDATE `tabCrane Driver Payroll` pay
        JOIN (
            SELECT parent, employee, SUM(overtime_hours) AS hours
            FROM `tabTimesheet Entry`
            WHERE parenttype = 'Crane Timesheet' AND parentfield = 'timesheet_entries'
            GROUP BY parent, employee
        ) shifts ON shifts.parent = pay.parent AND shifts.employee = pay.employee
        SET pay.overtime_hours = COALESCE(shifts.hours, 0)
        WHERE pay.parenttype = 'Crane Timesheet' AND pay.parentfield = 'driver_payroll'
    """)
