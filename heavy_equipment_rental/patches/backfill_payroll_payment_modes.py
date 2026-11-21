"""Show the actual payment mode on posted payroll rows."""

import frappe


def execute():
    if frappe.db.has_column("Crane Driver Payroll", "grouped_expense"):
        frappe.db.sql("""
            UPDATE `tabCrane Driver Payroll` payroll
            JOIN `tabGrouped Expense` expense ON expense.name = payroll.grouped_expense
            SET payroll.mode_of_payment = expense.mode_of_payment
            WHERE COALESCE(payroll.mode_of_payment, '') = ''
        """)
    frappe.db.sql("""
        UPDATE `tabCrane Driver Payroll` payroll
        JOIN `tabExpense Entry` expense ON expense.name = payroll.expense_entry
        SET payroll.mode_of_payment = expense.mode_of_payment
        WHERE payroll.parenttype = 'Crane Timesheet'
            AND payroll.parentfield = 'driver_payroll'
            AND COALESCE(payroll.mode_of_payment, '') = ''
            AND COALESCE(expense.mode_of_payment, '') != ''
    """)
