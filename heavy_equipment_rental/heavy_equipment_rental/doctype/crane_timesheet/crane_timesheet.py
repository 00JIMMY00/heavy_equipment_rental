from calendar import monthrange
from datetime import timedelta
from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.rental_validation import (
    assignment_doc,
    billable_totals,
    check_date_order,
    check_non_negative,
    crane_display_name,
    interval,
    lock_cranes,
    work_days,
)


@frappe.whitelist()
def default_timesheet_entries(period_start, period_end):
    if not frappe.has_permission("Crane Timesheet", "create"):
        frappe.throw(_("You cannot create Crane Timesheets."), frappe.PermissionError)
    check_date_order(period_start, period_end, _("Timesheet period"))
    start, end = getdate(period_start), getdate(period_end)
    if (end - start).days > 366:
        frappe.throw(_("Choose a timesheet period of at most 367 days."))
    settings = frappe.get_single("Heavy Equipment Rental Settings")
    settings.check_permission("read")
    return [{
        "work_date": str(start + timedelta(days=offset)),
        "start_time": str(settings.day_shift_start_time or "08:00:00"),
        "end_time": str(settings.day_shift_end_time or "16:00:00"),
        "ends_next_day": 0,
    } for offset in range((end - start).days + 1)]


def matching_assignments(crane, customer, location, start, end):
    """Only whole-period matches qualify. The caller chooses when several match."""
    if not all((crane, customer, location, start, end)):
        return []
    return frappe.db.sql("""SELECT DISTINCT a.name FROM `tabCrane Assignment` a
        JOIN `tabAssigned Crane` r ON r.parent=a.name AND r.parenttype='Crane Assignment'
        WHERE a.customer=%s AND a.location=%s AND r.crane=%s AND COALESCE(r.cancelled,0)=0
        AND r.start_date<=%s AND r.expected_end_date>=%s ORDER BY a.name""",
        (customer, location, crane, start, end), pluck=True)


@frappe.whitelist()
def find_assignments(crane, customer, location, period_start, period_end):
    if not frappe.has_permission("Crane Assignment", "read"):
        frappe.throw(_("You cannot read Crane Assignments."), frappe.PermissionError)
    check_date_order(period_start, period_end, _("Work period"))
    names = matching_assignments(crane, customer, location, period_start, period_end)
    return [name for name in names if frappe.has_permission("Crane Assignment", "read", name)]


@frappe.whitelist()
def get_timesheet_defaults(crane=None, selling_uom=None):
    if not frappe.has_permission("Crane Timesheet", "create"):
        frappe.throw(_("You cannot create Crane Timesheets."), frappe.PermissionError)
    settings = frappe.get_single("Heavy Equipment Rental Settings")
    settings.check_permission("read")
    unit = selling_uom or settings.default_selling_uom or "Hour"
    if unit not in ("Hour", "Day", "Month"):
        frappe.throw(_("Select an Hour, Day or Month Billing Unit."))
    defaults = {
        "rental_rate_unit": unit,
        "purchase_uom": settings.default_supplier_uom or "Hour",
    }
    if crane:
        equipment = frappe.get_doc("Crane", crane)
        equipment.check_permission("read")
        defaults["rental_rate"] = next((row.price for row in equipment.period_prices
                                        if row.period == unit), 0)
    return defaults


class CraneTimesheet(Document):
    def before_validate(self):
        previous = self.get_doc_before_save()
        if self.is_new():
            defaults = get_timesheet_defaults(self.crane, self.rental_rate_unit)
            self.purchase_uom = self.purchase_uom or defaults["purchase_uom"]
            if not self.assignment:
                default_price = self.rental_rate is None or (not self.rental_rate and not self.rental_rate_unit)
                self.rental_rate_unit = self.rental_rate_unit or defaults["rental_rate_unit"]
                if default_price:
                    self.rental_rate = defaults.get("rental_rate", 0)
        if not previous or previous.docstatus == 0:
            crane = frappe.get_doc("Crane", self.crane) if self.crane else None
            if crane:
                crane.check_permission("read")
            self.crane_ownership_type = crane.ownership_type if crane else None
            self.purchase_supplier = crane.supplier if crane and crane.ownership_type == "Rented" else None
            if self.crane_ownership_type != "Rented":
                self.rented = 0
        if self.driver:
            for row in self.timesheet_entries:
                if not row.employee:
                    row.employee = self.driver
        if self.assignment:
            rental = assignment_doc(self.assignment, "read")
            self.customer = self.customer or rental.customer
            self.location = self.location or rental.location
            return
        if not all((self.crane, self.customer, self.location, self.period_start, self.period_end)):
            return
        matches = matching_assignments(
            self.crane, self.customer, self.location, self.period_start, self.period_end)
        if len(matches) > 1:
            frappe.throw(_("Several assignments cover this work. Choose the Crane Assignment on the Timesheet."))
        if matches:
            assignment_doc(matches[0], "read")
            self.assignment = matches[0]
            return
        if not self.rental_rate_unit or self.rental_rate is None:
            frappe.throw(_("No assignment covers this work. Enter the billing unit and agreed rate."))
        check_date_order(self.period_start, self.period_end, _("Rental period"))
        if not frappe.has_permission("Crane Assignment", "create"):
            frappe.throw(_("Creating a rental requires Crane Assignment create permission."), frappe.PermissionError)
        assignment = frappe.get_doc({
            "doctype": "Crane Assignment", "customer": self.customer,
            "location": self.location,
            "assigned_cranes": [{
                "crane": self.crane, "start_date": self.period_start,
                "expected_end_date": self.period_end,
                "rental_rate_unit": self.rental_rate_unit,
                "rental_rate": self.rental_rate,
            }],
        })
        assignment.insert()
        self.assignment = assignment.name

    def before_update_after_submit(self):
        before = self.get_doc_before_save()
        if before and self.sales_invoice != before.sales_invoice:
            frappe.throw(_("The Sales Invoice link is managed by Generate Sales Invoice."))
        if before and self.purchase_invoice != before.purchase_invoice:
            frappe.throw(_("The Purchase Invoice link is managed automatically."))

    def validate(self):
        previous = self.get_doc_before_save()
        if (self.purchase_invoice or None) != (previous.purchase_invoice if previous else None):
            frappe.throw(_("The Purchase Invoice link is managed automatically."))
        # Submitted amounts are snapshots. Attachment edits must not recalculate them.
        # Frappe still rejects changes to fields that do not allow edits after submission.
        if previous and previous.docstatus == self.docstatus == 1:
            return
        if self.crane_ownership_type == "Rented" and self.rented and self.docstatus != 2 and not (
            previous and previous.docstatus == 1
        ):
            if not self.purchase_supplier:
                frappe.throw(_("Select a Supplier on the rented Crane first."))
            if self.purchase_uom not in ("Hour", "Day", "Month"):
                frappe.throw(_("Select an Hour, Day or Month Supplier Billing UOM."))
            if flt(self.purchase_rate) <= 0:
                frappe.throw(_("Enter a positive Purchase Price per {0}.").format(self.purchase_uom))
        check_date_order(self.period_start, self.period_end, _("Timesheet period"))
        if not self.assignment:
            frappe.throw(_("Select a Crane Assignment or enter billing terms for a new rental."))
        lock_cranes([self.crane])
        assignment = assignment_doc(self.assignment, "read", lock=True)
        if self.customer != assignment.customer or self.location != assignment.location:
            frappe.throw(_("Timesheet customer and location must match the Assignment."))
        bookings = [row for row in assignment.assigned_cranes
                    if row.crane == self.crane and not row.cancelled]
        if not bookings:
            frappe.throw(_("Crane {0} is not in this Assignment.").format(crane_display_name(self.crane)))
        if not previous or previous.docstatus == 0:
            covering = [row for row in bookings if getdate(row.start_date) <= getdate(self.period_start)
                        and getdate(row.expected_end_date) >= getdate(self.period_end)]
            if len(covering) == 1:
                self.rental_rate_unit = covering[0].rental_rate_unit
                self.rental_rate = covering[0].rental_rate
        if self.amended_from:
            source = frappe.get_doc("Crane Timesheet", self.amended_from, for_update=True)
            source.check_permission("amend")
            if source.docstatus != 2 or source.assignment != self.assignment or source.crane != self.crane:
                frappe.throw(_("Amend a cancelled Timesheet for the same Assignment and crane."))
        if not self.timesheet_entries and self.docstatus == 1:
            frappe.throw(_("Add at least one shift before submitting the Timesheet."))
        intervals, operator_hours, flat_days, flat_rows = [], 0, {}, []
        submitted_update = bool(previous and previous.docstatus == 1 and self.docstatus == 1)
        employees = {row.employee for row in self.timesheet_entries if row.employee}
        driver_names = {row.name: row.employee_name for row in frappe.get_all(
            "Employee", filters={"name": ["in", list(employees)]},
            fields=["name", "employee_name"])} if employees else {}
        hours_by_driver = {}
        start_period, end_period = getdate(self.period_start), getdate(self.period_end)
        for row in self.timesheet_entries:
            start, end = interval(row)
            days = list(work_days(start, end))
            for day in days:
                if day > getdate(today()):
                    frappe.throw(_("Row {0}: future work cannot be recorded.").format(row.idx))
                if not start_period <= day <= end_period:
                    frappe.throw(_("Row {0}: work is outside the Timesheet period.").format(row.idx))
                if not any(getdate(booking.start_date) <= day <= getdate(booking.expected_end_date)
                           for booking in bookings):
                    frappe.throw(_("Row {0}: work falls outside the agreed rental dates. Extend the Assignment deliberately.").format(row.idx))
            hours = (end - start).total_seconds() / 3600
            check_non_negative(row.overtime_hours, _("Row {0} overtime").format(row.idx))
            if flt(row.overtime_hours) > hours:
                frappe.throw(_("Row {0}: overtime cannot exceed worked hours.").format(row.idx))
            # Agreed hourly pricing belongs to the rental, not individual operators.
            matching = [booking for booking in bookings if all(
                getdate(booking.start_date) <= day <= getdate(booking.expected_end_date) for day in days)]
            if len(matching) != 1:
                frappe.throw(_("Row {0}: a shift must fit exactly one booked crane period.").format(row.idx))
            booking = matching[0]
            row.price_per_hour = booking.rental_rate if booking.rental_rate_unit == "Hour" else 0
            row.worked_hours = hours
            if not submitted_update:
                row.driver_name = driver_names.get(row.employee)
            hours_by_driver[row.employee] = hours_by_driver.get(row.employee, 0) + hours
            row.line_amount = hours * flt(row.price_per_hour)
            if booking.rental_rate_unit in ("Day", "Month"):
                for day in days:
                    flat_days[(booking.name, day)] = booking
                flat_rows.append(row)
            operator_hours += hours
            intervals.append((start, end, flt(row.price_per_hour)))
        if not submitted_update:
            self.set("driver_hours", [])
            for employee, hours in hours_by_driver.items():
                self.append("driver_hours", {
                    "employee": employee,
                    "driver_name": driver_names.get(employee),
                    "total_hours": hours,
                })
        self.total_operator_hours = operator_hours
        self.total_crane_billable_hours, hourly_amount = billable_totals(intervals)
        flat_amount = sum(
            Decimal(str(booking.rental_rate)) * (
                Decimal(1) if booking.rental_rate_unit == "Day" else
                Decimal(1) / Decimal(monthrange(day.year, day.month)[1]))
            for (_, day), booking in flat_days.items()
        )
        flat_operator_hours = sum(row.worked_hours for row in flat_rows)
        if flat_operator_hours:
            for row in flat_rows:
                row.line_amount = float(flat_amount) * row.worked_hours / flat_operator_hours
        for row in self.timesheet_entries:
            row.line_amount = flt(row.line_amount, row.precision("line_amount"))
        self.total_amount = flt(hourly_amount + float(flat_amount), self.precision("total_amount"))
        if intervals:
            existing = frappe.db.sql("""SELECT e.*, s.name AS timesheet FROM `tabTimesheet Entry` e
                JOIN `tabCrane Timesheet` s ON s.name=e.parent
                WHERE e.parenttype='Crane Timesheet' AND s.crane=%s AND s.docstatus=1 AND s.name!=%s
                AND e.work_date BETWEEN %s AND %s FOR UPDATE""",
                (self.crane, self.name or "", min(s.date() for s, _, _ in intervals) - timedelta(days=1),
                 max(e.date() for _, e, _ in intervals)), as_dict=True)
            for other in existing:
                other_start, other_end = interval(other)
                if any(start < other_end and other_start < end for start, end, _ in intervals):
                    frappe.throw(_("Crane {0}: shift overlaps submitted Timesheet {1}.").format(
                        crane_display_name(self.crane), other.timesheet))

    def on_submit(self):
        if self.crane_ownership_type == "Rented" and self.rented:
            from heavy_equipment_rental.purchasing import create_purchase_invoice

            create_purchase_invoice(self)

    def before_cancel(self):
        lock_cranes([self.crane])
        assignment_doc(self.assignment, "read", lock=True)
        if self.purchase_invoice and frappe.db.get_value("Purchase Invoice", self.purchase_invoice, "docstatus") != 2:
            frappe.throw(_("Cancel Purchase Invoice {0} before cancelling this Timesheet.").format(self.purchase_invoice))
        invoice = frappe.db.get_value("Crane Timesheet", self.name, "sales_invoice")
        if invoice and frappe.db.exists("Sales Invoice", invoice):
            if frappe.db.get_value("Sales Invoice", invoice, "docstatus") != 2:
                frappe.throw(_("Cancel Sales Invoice {0} before cancelling this Timesheet.").format(invoice))
