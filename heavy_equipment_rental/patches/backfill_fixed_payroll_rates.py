"""Display the implied rate for existing payroll amounts."""

import frappe

from heavy_equipment_rental.driver_payroll import implied_payroll_rate


def execute():
    payroll = frappe.qb.DocType("Crane Driver Payroll")
    rows = (
        frappe.qb.from_(payroll)
        .select(payroll.name)
        .where(payroll.parenttype == "Crane Timesheet")
        .where(payroll.parentfield == "driver_payroll")
        .where(payroll.amount > 0)
        .where((payroll.rate == 0) | payroll.rate.isnull())
        .run(pluck=True)
    )
    for name in rows:
        row = frappe.get_doc("Crane Driver Payroll", name)
        frappe.db.set_value(row.doctype, name, {
            "fixed_amount": 1,
            "rate": implied_payroll_rate(row),
        }, update_modified=False)
