"""Retire monthly defaults and convert draft payroll from recorded regular hours."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from heavy_equipment_rental.driver_payroll import driver_work_summary


def execute():
    # Move the original child records out of the active Crane and Item grids.
    # Their parent, price, name and audit timestamps remain available for review.
    frappe.db.sql("""update `tabCrane Period Price` set parentfield = 'legacy_month_prices'
        where parentfield = 'period_prices' and parenttype in ('Crane', 'Item') and period = 'Month'""")
    frappe.db.sql("update `tabCrane` set default_selling_uom = 'Hour' where default_selling_uom = 'Month'")
    for field in ("default_selling_uom", "default_supplier_uom"):
        if frappe.db.get_single_value("Heavy Equipment Rental Settings", field) == "Month":
            frappe.db.set_single_value("Heavy Equipment Rental Settings", field, "Hour")

    parents = frappe.get_all("Crane Driver Payroll", filters={
        "parenttype": "Crane Timesheet", "docstatus": 0, "unit": ["in", ["Day", "Month"]],
    }, pluck="parent", distinct=True)
    for name in parents:
        sheet = frappe.get_doc("Crane Timesheet", name)
        if sheet.docstatus:
            continue
        regular = defaultdict(float)
        for shift in sheet.timesheet_entries:
            regular[shift.employee] += flt(shift.worked_hours)
        summary = driver_work_summary(sheet)
        for row in sheet.driver_payroll:
            if row.unit not in ("Day", "Month"):
                continue
            values = dict(summary.get(row.employee, dict(unit="Hour", quantity=0, worked_hours=0)))
            hours = values["quantity"]
            if row.fixed_amount or (row.amount and not row.rate):
                values.update(fixed_amount=1, rate=flt(row.amount / hours, 9) if hours else 0)
            else:
                # An overtime-only draft has no regular baseline. Keep its earned
                # amount as the starting value. With no work, a new rate is needed.
                baseline = regular[row.employee] or hours
                rate = flt(row.amount / baseline, 9) if baseline else 0
                values.update(rate=rate, amount=flt(rate * hours, row.precision("amount")))
            frappe.db.set_value(row.doctype, row.name, values, update_modified=False)
        sheet.db_set("modified", frappe.utils.now(), update_modified=False)
