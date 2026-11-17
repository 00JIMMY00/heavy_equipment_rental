"""Show the actual payment mode on posted payroll rows."""

import frappe


def execute():
    frappe.db.sql("""
        UPDATE `tabCrane Driver Payroll` payroll
        JOIN `tabExpense Entry` expense ON expense.name = payroll.expense_entry
        SET payroll.mode_of_payment = expense.mode_of_payment
        WHERE payroll.parenttype = 'Crane Timesheet'
            AND payroll.parentfield = 'driver_payroll'
            AND COALESCE(payroll.mode_of_payment, '') = ''
            AND COALESCE(expense.mode_of_payment, '') != ''
    """)
