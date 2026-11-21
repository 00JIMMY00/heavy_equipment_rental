from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import getdate

from heavy_equipment_rental.employee_salary import SALARY_FIELDS, money, monthly_paid, salary_accounts


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company or not filters.month:
        frappe.throw(_("Select a Company and a Salary Month."))

    company = frappe.get_doc("Company", filters.company)
    company.check_permission("read")
    month = getdate(filters.month)
    employees = frappe.get_all(
        "Employee", filters={"company": company.name}, fields=["name", "employee_name", *SALARY_FIELDS],
        order_by="employee_name, name",
    )
    paid_by_employee = monthly_paid(
        company.name, salary_accounts(company.name), [employee.name for employee in employees], month,
    )

    data = []
    for employee in employees:
        basic, kpi = (money(employee[field]) for field in SALARY_FIELDS)
        paid = paid_by_employee.get(employee.name, Decimal(0))
        basic_paid = min(basic, paid)
        kpi_paid = min(kpi, paid - basic_paid)
        data.append(dict(
            employee=employee.name, employee_name=employee.employee_name, currency=company.default_currency,
            basic_salary=basic, kpi_incentive=kpi, basic_paid=basic_paid, kpi_paid=kpi_paid, total_paid=paid,
            basic_due=basic - basic_paid, kpi_due=kpi - kpi_paid, total_due=basic + kpi - basic_paid - kpi_paid,
        ))

    return columns(), data, _(
        "The report uses current employee salary amounts and submitted salary expenses in company currency. "
        "Payments are applied to basic salary first, then to the KPI incentive."
    )


def columns():
    return [
        dict(fieldname="employee", label=_("Employee"), fieldtype="Link", options="Employee", width=135),
        dict(fieldname="employee_name", label=_("Employee Name"), fieldtype="Data", width=170),
        *[
            dict(fieldname=fieldname, label=_(label), fieldtype="Currency", options="currency", width=135)
            for fieldname, label in (
                ("basic_salary", "Basic Salary"), ("kpi_incentive", "KPI Incentive"),
                ("basic_paid", "Basic Paid"), ("kpi_paid", "KPI Paid"), ("total_paid", "Total Paid"),
                ("basic_due", "Basic Remaining"), ("kpi_due", "KPI Remaining"), ("total_due", "Total Due"),
            )
        ],
    ]
