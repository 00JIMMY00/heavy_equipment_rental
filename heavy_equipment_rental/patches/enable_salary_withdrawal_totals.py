"""Enable totals on existing Employee Salary Withdrawals reports."""

import frappe


def execute():
    # Frappe preserves add_total_row when syncing an existing Report.
    frappe.db.set_value("Report", "Employee Salary Withdrawals", "add_total_row", 1)
