import frappe
from frappe import _
from frappe.utils import getdate

from heavy_equipment_rental.employee_salary import monthly_paid, salary_accounts


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company or not filters.month:
        frappe.throw(_("Select a Company and a Salary Month."))

    company = frappe.get_doc("Company", filters.company)
    company.check_permission("read")
    month = getdate(filters.month)
    employees = frappe.get_all(
        "Employee", filters={"company": company.name}, fields=["name", "employee_name"],
        order_by="employee_name, name",
    )
    paid_by_employee = monthly_paid(
        company.name, salary_accounts(company.name), [employee.name for employee in employees], month,
    )

    data = [
        dict(employee=row.name, employee_name=row.employee_name, currency=company.default_currency,
             total_paid=paid_by_employee.get(row.name, 0))
        for row in employees
    ]
    columns = [
        dict(fieldname="employee", label=_("Employee"), fieldtype="Link", options="Employee", width=135),
        dict(fieldname="employee_name", label=_("Employee Name"), fieldtype="Data", width=170),
        dict(fieldname="total_paid", label=_("Total Salary Withdrawals"), fieldtype="Currency",
             options="currency", width=165),
    ]
    return columns, data, None
