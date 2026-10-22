"""Permission-filtered rental and crane dashboard reads."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate, today

from heavy_equipment_rental.rental_validation import (
    allocation_window, allocations, check_date_order, entry_days, ranges_overlap,
)


def visible_allocations(assignment=None, crane=None):
    parents = frappe.get_list("Crane Assignment", filters={"name": assignment} if assignment else {},
                              fields=["name", "customer", "location"], limit_page_length=0)
    if not parents:
        return []
    cranes = frappe.get_list("Crane", filters={"name": crane} if crane else {},
                             fields=["name", "crane_name"], limit_page_length=0)
    if not cranes:
        return []
    parent_map = {row.name: row for row in parents}
    crane_map = {row.name: row.crane_name for row in cranes}
    rows = frappe.get_all("Assigned Crane", filters={
        "parent": ["in", list(parent_map)], "parenttype": "Crane Assignment",
        "crane": ["in", list(crane_map)], "cancelled": 0,
    }, fields=["name", "parent", "crane", "start_date", "expected_end_date",
               "rental_rate", "rental_rate_unit", "cancelled"],
       order_by="crane,start_date,idx", limit_page_length=0)
    for row in rows:
        row.assignment = row.parent
        row.customer = parent_map[row.parent].customer
        row.location = parent_map[row.parent].location
        row.crane_name = crane_map[row.crane]
    return rows


@frappe.whitelist()
def crane_availability(crane, date=None, to_date=None):
    doc = frappe.get_doc("Crane", crane)
    doc.check_permission("read")
    start, end = getdate(date or today()), getdate(to_date or date or today())
    check_date_order(start, end, _("Availability period"))
    all_rows = allocations([crane], lock=False)
    current = [row for row in all_rows if allocation_window(row) and
               ranges_overlap(start, end, *allocation_window(row))]
    future = [row for row in all_rows if getdate(row.start_date) > end]
    visible = {row.name: row for row in visible_allocations(crane=crane)}
    work = frappe.db.sql("""SELECT e.* FROM `tabTimesheet Entry` e
        JOIN `tabCrane Timesheet` s ON s.name=e.parent
        WHERE e.parenttype='Crane Timesheet' AND s.crane=%s AND s.docstatus<2
        AND e.work_date BETWEEN %s AND %s""",
        (crane, start - timedelta(days=1), end), as_dict=True)
    has_work = any(start <= day <= end for row in work for day in entry_days(row))
    available = not current and doc.operational_condition != "Inactive"
    indicators = []
    if current:
        indicators.append("Booked for selected dates")
    if len(current) > 1 and start == end:
        indicators.append("Overlapping bookings need review")
    if any(not row.rental_rate for row in current):
        indicators.append("Agreed rate missing on a booking")
    if has_work:
        indicators.append("Work recorded")
    if future:
        indicators.append("Upcoming booking")
    if available:
        indicators.append("Available for selected dates")
    if doc.operational_condition != "Operational":
        indicators.append(doc.operational_condition)
    sheets = frappe.get_list("Crane Timesheet", filters={"crane": crane},
                             fields=["name", "assignment", "sales_invoice", "docstatus"],
                             limit_page_length=0) if frappe.has_permission("Crane Timesheet", "read") else []
    invoices = sorted({s.sales_invoice for s in sheets if s.sales_invoice and
                       frappe.has_permission("Sales Invoice", "read", s.sales_invoice)})
    expenses = frappe.get_list("Expense Entry", filters={"crane": crane},
                               fields=["name", "amount", "docstatus"], limit_page_length=0) \
        if frappe.has_permission("Expense Entry", "read") else []
    maintenance = frappe.get_list("Crane Maintenance", filters={"crane": crane},
                                  fields=["name", "status", "cost", "planned_start_date"],
                                  limit_page_length=0) \
        if frappe.has_permission("Crane Maintenance", "read") else []
    return {
        "date": start, "to_date": end, "available": available,
        "operational_condition": doc.operational_condition, "indicators": indicators,
        "work_recorded": has_work,
        "bookings": [visible[row.name] for row in current if row.name in visible],
        "future_reservations": [visible[row.name] for row in future if row.name in visible],
        "timesheets": sheets, "invoices": invoices, "expenses": expenses,
        "maintenance": maintenance,
    }
