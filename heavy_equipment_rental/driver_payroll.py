"""Post driver pay from a Crane Timesheet through HER Expense Entries."""

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
    expense_type = frappe.db.get_value(
        "Expense Entry Type", row.expense_type, ["company", "enabled"], as_dict=True
    ) if row.expense_type else None
    if not expense_type or not expense_type.enabled or expense_type.company != row.company:
        frappe.throw(_("Select an enabled driver payroll Expense Entry Type for {0}.").format(row.company))
    account = payment_account(row.mode_of_payment, row.company)
    if frappe.db.get_value("Account", account, "disabled"):
        frappe.throw(_("Select a payroll Mode of Payment with an enabled account for {0}.").format(row.company))


def sync_payroll_rows(sheet, company, employees):
    sheet.payroll_company = company
    seen = set()
    for row in list(sheet.driver_payroll):
        if row.expense_entry:
            frappe.throw(_("Driver payroll Expense Entry links are managed automatically."))
        amount = flt(row.amount)
        if not isfinite(amount) or amount < 0:
            frappe.throw(_("Driver payroll row {0}: Enter a finite, non-negative amount.").format(row.idx))
        if row.employee not in employees:
            if amount:
                frappe.throw(_("Driver payroll row {0}: Clear the amount for the driver who is no longer on an operator shift.").format(row.idx))
            sheet.remove(row)
            continue
        if row.employee in seen:
            frappe.throw(_("Enter only one payroll amount per driver."))
        seen.add(row.employee)
        if amount and frappe.db.get_value("Employee", row.employee, "company") != company:
            frappe.throw(_("Driver {0} must belong to the Timesheet company to receive payroll.").format(row.employee))

    for employee in employees:
        if employee not in seen:
            sheet.append("driver_payroll", {"employee": employee})


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
