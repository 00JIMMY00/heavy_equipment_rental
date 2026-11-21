from calendar import monthrange
from datetime import timedelta
from decimal import Decimal
from math import isfinite

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from heavy_equipment_rental.driver_payroll import (
    cancel_driver_payroll,
    driver_work_summary,
    payroll_defaults,
    post_driver_payroll,
    sync_payroll_rows,
)
from heavy_equipment_rental.rental_validation import (
    assignment_doc,
    crane_company,
    validate_rental_asset,
    entered_hour_totals,
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
        "work_date": str(day),
        "day_name": day_name(day),
        "start_time": str(settings.day_shift_start_time or "08:00:00"),
        "end_time": str(settings.day_shift_end_time or "16:00:00"),
        "ends_next_day": 0,
        "worked_hours": flt(settings.day_shift_hours or 8),
    } for day in (start + timedelta(days=offset) for offset in range((end - start).days + 1))]


def day_name(day):
    return ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[day.weekday()]


def matching_assignments(crane, customer, location, start, end):
    """Only whole-period matches qualify. The caller chooses when several match."""
    if not all((crane, customer, location, start, end)):
        return []
    return frappe.db.sql("""SELECT DISTINCT a.name FROM `tabRental Contract` a
        JOIN `tabAssigned Crane` r ON r.parent=a.name AND r.parenttype='Rental Contract'
        WHERE a.customer=%s AND a.location=%s AND r.crane=%s AND COALESCE(r.cancelled,0)=0
        AND r.start_date<=%s AND r.expected_end_date>=%s ORDER BY a.name""",
        (customer, location, crane, start, end), pluck=True)


@frappe.whitelist()
def find_assignments(crane, customer, location, period_start, period_end):
    if not frappe.has_permission("Rental Contract", "read"):
        frappe.throw(_("You cannot read Rental Contracts."), frappe.PermissionError)
    check_date_order(period_start, period_end, _("Work period"))
    names = matching_assignments(crane, customer, location, period_start, period_end)
    return [name for name in names if frappe.has_permission("Rental Contract", "read", name)]


@frappe.whitelist()
def get_timesheet_defaults(crane=None, selling_uom=None):
    if not frappe.has_permission("Crane Timesheet", "create"):
        frappe.throw(_("You cannot create Crane Timesheets."), frappe.PermissionError)
    settings = frappe.get_single("Heavy Equipment Rental Settings")
    settings.check_permission("read")
    unit = selling_uom or (frappe.get_cached_value("Crane", crane, "default_selling_uom") if crane else None) or settings.default_selling_uom or "Hour"
    if unit not in ("Hour", "Day"):
        frappe.throw(_("Select an Hour or Day Billing Unit."))
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


@frappe.whitelist()
def get_default_payroll_mode(assignment):
    frappe.get_cached_doc("Heavy Equipment Rental Settings").check_permission("read")
    company = assignment_doc(assignment, "read").company
    default = payroll_defaults(company)
    return default.mode_of_payment if default else None


class CraneTimesheet(Document):
    def before_validate(self):
        previous = self.get_doc_before_save()
        if self.is_new():
            defaults = get_timesheet_defaults(self.crane, None if self.assignment else self.rental_rate_unit)
            self.purchase_uom = self.purchase_uom or defaults["purchase_uom"]
        if not previous or previous.docstatus == 0:
            crane = frappe.get_doc("Crane", self.crane) if self.crane else None
            if crane:
                crane.check_permission("read")
            self.crane_ownership_type = ("Rented" if crane.hired_from_supplier else ("Other" if crane.ownership_type == "Rented" else crane.ownership_type)) if crane else None
            self.purchase_supplier = crane.supplier if crane and crane.hired_from_supplier else None
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
            frappe.throw(_("Several rental contracts cover this work. Choose the Rental Contract on the Timesheet."))
        if matches:
            assignment_doc(matches[0], "read")
            self.assignment = matches[0]
            return
        if self.is_new():
            default_price = self.rental_rate is None or (not self.rental_rate and not self.rental_rate_unit)
            self.rental_rate_unit = self.rental_rate_unit or defaults["rental_rate_unit"]
            if default_price:
                self.rental_rate = defaults.get("rental_rate", 0)
        if not self.rental_rate_unit or self.rental_rate is None:
            frappe.throw(_("No rental contract covers this work. Enter the billing unit and agreed rate."))
        check_date_order(self.period_start, self.period_end, _("Rental period"))
        if not frappe.has_permission("Rental Contract", "create"):
            frappe.throw(_("Creating a rental requires Rental Contract create permission."), frappe.PermissionError)
        assignment = frappe.get_doc({
            "doctype": "Rental Contract", "customer": self.customer,
            "company": crane_company(self.crane) or frappe.defaults.get_user_default("Company"),
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
        if before and self.profit_settlement != before.profit_settlement:
            frappe.throw(_("The Profit Settlement link is managed automatically."))
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
        if previous and previous.docstatus == 1 and self.docstatus in (1, 2):
            return
        check_date_order(self.period_start, self.period_end, _("Timesheet period"))
        if not self.assignment:
            frappe.throw(_("Select a Rental Contract or enter billing terms for a new rental."))
        lock_cranes([self.crane])
        if self.docstatus != 2:
            validate_rental_asset(self.crane)
        assignment = assignment_doc(self.assignment, "read", lock=True)
        if self.customer != assignment.customer or self.location != assignment.location:
            frappe.throw(_("Timesheet customer and location must match the Rental Contract."))
        bookings = [row for row in assignment.assigned_cranes
                    if row.crane == self.crane and not row.cancelled]
        if not bookings:
            frappe.throw(_("Crane {0} is not in this Rental Contract.").format(crane_display_name(self.crane)))
        source = None
        if self.amended_from:
            source = frappe.get_doc("Crane Timesheet", self.amended_from, for_update=True)
            source.check_permission("amend")
            if source.docstatus != 2 or source.assignment != self.assignment or source.crane != self.crane:
                frappe.throw(_("Amend a cancelled Timesheet for the same Rental Contract and crane."))
        if not previous or previous.docstatus == 0:
            covering = [row for row in bookings if getdate(row.start_date) <= getdate(self.period_start)
                        and getdate(row.expected_end_date) >= getdate(self.period_end)]
            if len(covering) == 1:
                if not self.rental_rate_unit:
                    self.rental_rate_unit = covering[0].rental_rate_unit
                    self.rental_rate = covering[0].rental_rate
                elif self.rental_rate is None:
                    self.rental_rate = covering[0].rental_rate
            legacy_month = self.rental_rate_unit == "Month" and (
                any(doc and doc.rental_rate_unit == "Month" for doc in (previous, source)) or
                (len(covering) == 1 and covering[0].rental_rate_unit == "Month")
            )
            if self.rental_rate_unit and ((self.rental_rate_unit not in ("Hour", "Day") and not legacy_month) or flt(self.rental_rate) <= 0):
                frappe.throw(_("Enter a positive agreed rate and an Hour or Day Billing Unit."))
        if self.purchase_uom == "Month" and not any(
            doc and doc.purchase_uom == "Month" for doc in (previous, source)
        ):
            frappe.throw(_("Select an Hour or Day Supplier Billing UOM."))
        if not self.timesheet_entries and self.docstatus == 1:
            frappe.throw(_("Add at least one shift before submitting the Timesheet."))
        operator_hours, flat_days, flat_rows = 0, {}, []
        entered_intervals = []
        overtime_intervals = []
        driver_intervals = {}
        crane_hour_price = next((flt(row.price) for row in frappe.get_doc("Crane", self.crane).period_prices
                                 if row.period == "Hour"), 0)
        submitted_update = bool(previous and previous.docstatus == 1 and self.docstatus == 1)
        employees = {row.employee for row in self.timesheet_entries if row.employee}
        driver_names = {row.name: row.employee_name for row in frappe.get_all(
            "Employee", filters={"name": ["in", list(employees)]},
            fields=["name", "employee_name"])} if employees else {}
        start_period, end_period = getdate(self.period_start), getdate(self.period_end)
        for row in self.timesheet_entries:
            if not row.work_date:
                frappe.throw(_("Row {0}: a work date is required.").format(row.idx))
            day = getdate(row.work_date)
            row.day_name = day_name(day)
            if row.worked_hours is not None and flt(row.worked_hours) == 0 and not flt(row.overtime_hours):
                days = [day]
            else:
                start, end = interval(row)
                days = list(work_days(start, end))
                # Initialize omitted legacy/API values once from clock times.
                if row.worked_hours is None:
                    row.worked_hours = (end - start).total_seconds() / 3600
            for day in days:
                if not start_period <= day <= end_period:
                    frappe.throw(_("Row {0}: work is outside the Timesheet period.").format(row.idx))
                if not any(getdate(booking.start_date) <= day <= getdate(booking.expected_end_date)
                           for booking in bookings):
                    frappe.throw(_("Row {0}: work falls outside the agreed rental dates. Extend the Rental Contract deliberately.").format(row.idx))
            hours = flt(row.worked_hours)
            if not isfinite(hours) or hours < 0:
                frappe.throw(_("Row {0}: Worked Hours must be a finite non-negative number.").format(row.idx))
            check_non_negative(row.overtime_hours, _("Row {0} overtime").format(row.idx))
            check_non_negative(row.overtime_price, _("Price for Overtime"))
            if not isfinite(flt(row.overtime_hours)) or not isfinite(flt(row.overtime_price)):
                frappe.throw(_("Row {0}: overtime hours and price must be finite.").format(row.idx))
            # Agreed hourly pricing belongs to the rental, not individual operators.
            matching = [booking for booking in bookings if all(
                getdate(booking.start_date) <= day <= getdate(booking.expected_end_date) for day in days)]
            if len(matching) != 1:
                frappe.throw(_("Row {0}: a shift must fit exactly one booked crane period.").format(row.idx))
            booking = frappe._dict(matching[0].as_dict())
            if self.rental_rate_unit:
                booking.rental_rate_unit = self.rental_rate_unit
                booking.rental_rate = self.rental_rate
            if not submitted_update:
                row.rental_rate = booking.rental_rate
                row.rental_rate_unit = booking.rental_rate_unit
            row.price_per_hour = booking.rental_rate if booking.rental_rate_unit == "Hour" else 0
            row.effective_overtime_price = flt(row.overtime_price) or (
                flt(booking.rental_rate) if booking.rental_rate_unit == "Hour" else crane_hour_price)
            if flt(row.overtime_hours) > 0 and row.effective_overtime_price <= 0:
                frappe.throw(_("Row {0}: enter an overtime price or set the Crane Hour price.").format(row.idx))
            if not submitted_update:
                row.driver_name = driver_names.get(row.employee)
            row.line_amount = hours * flt(row.price_per_hour)
            if hours > 0 and booking.rental_rate_unit in ("Day", "Month"):
                for day in days:
                    flat_days[(booking.name, day)] = booking
                flat_rows.append(row)
            if hours or flt(row.overtime_hours):
                if not row.employee:
                    frappe.throw(_("Row {0}: select a Driver when recording worked hours or overtime.").format(row.idx),
                                 frappe.MandatoryError)
                driver_intervals.setdefault(row.employee, []).append((start, end, row.idx))
            operator_hours += hours + flt(row.overtime_hours)
            if hours > 0:
                entered_intervals.append((start, end, flt(row.price_per_hour), hours))
            if flt(row.overtime_hours) > 0:
                overtime_intervals.append((start, end, row.effective_overtime_price, flt(row.overtime_hours)))
        for shifts in driver_intervals.values():
            shifts.sort()
            for previous_shift, shift in zip(shifts, shifts[1:]):
                if shift[0] < previous_shift[1]:
                    frappe.throw(_("Rows {0} and {1}: the same driver cannot work overlapping shifts.").format(
                        previous_shift[2], shift[2]))
        if not submitted_update:
            driver_work = driver_work_summary(self)
            sync_payroll_rows(self, assignment.company, driver_work)
            self.set("driver_hours", [])
            for employee, work in driver_work.items():
                self.append("driver_hours", {
                    "employee": employee,
                    "driver_name": driver_names.get(employee),
                    "total_hours": work["worked_hours"],
                })
        self.total_operator_hours = operator_hours
        regular_hours, hourly_amount = entered_hour_totals(entered_intervals)
        self.total_overtime_hours, self.total_overtime_amount = entered_hour_totals(overtime_intervals)
        self.total_crane_billable_hours = regular_hours + self.total_overtime_hours
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
            row.line_amount += flt(row.overtime_hours) * row.effective_overtime_price
            row.line_amount = flt(row.line_amount, row.precision("line_amount"))
        self.total_amount = flt(hourly_amount + float(flat_amount) + self.total_overtime_amount, self.precision("total_amount"))
        if (self.total_crane_billable_hours > 0 and self.crane_ownership_type == "Rented" and self.rented
            and self.docstatus != 2 and not (previous and previous.docstatus == 1)):
            if not self.purchase_supplier:
                frappe.throw(_("Select a Supplier on the rented Crane first."))
            if self.purchase_uom not in ("Hour", "Day", "Month"):
                frappe.throw(_("Select an Hour or Day Supplier Billing UOM."))
            if flt(self.purchase_rate) <= 0:
                frappe.throw(_("Enter a positive Purchase Price per {0}.").format(self.purchase_uom))
        worked_intervals = entered_intervals + overtime_intervals
        if worked_intervals:
            existing = frappe.db.sql("""SELECT e.*, s.name AS timesheet FROM `tabTimesheet Entry` e
                JOIN `tabCrane Timesheet` s ON s.name=e.parent
                WHERE e.parenttype='Crane Timesheet' AND s.crane=%s AND s.docstatus=1 AND s.name!=%s
                AND (e.worked_hours > 0 OR e.overtime_hours > 0 OR e.worked_hours IS NULL)
                AND e.work_date BETWEEN %s AND %s FOR UPDATE""",
                (self.crane, self.name or "", min(s.date() for s, _, _, _ in worked_intervals) - timedelta(days=1),
                 max(e.date() for _, e, _, _ in worked_intervals)), as_dict=True)
            for other in existing:
                other_start, other_end = interval(other)
                if other_start == other_end:
                    continue
                if any(start < other_end and other_start < end for start, end, _, _ in worked_intervals):
                    frappe.throw(_("Crane {0}: shift overlaps submitted Timesheet {1}.").format(
                        crane_display_name(self.crane), other.timesheet))

    def on_submit(self):
        if self.crane_ownership_type == "Rented" and self.rented and self.total_crane_billable_hours > 0:
            from heavy_equipment_rental.purchasing import create_purchase_invoice

            create_purchase_invoice(self)
        post_driver_payroll(self)

    def before_cancel(self):
        from heavy_equipment_rental.cancellation import cancel_timesheet_dependencies
        lock_cranes([self.crane])
        assignment_doc(self.assignment, "read", lock=True)
        cancel_timesheet_dependencies(self)
        if self.purchase_invoice and frappe.db.get_value("Purchase Invoice", self.purchase_invoice, "docstatus") != 2:
            frappe.throw(_("Cancel Purchase Invoice {0} before cancelling this Timesheet.").format(self.purchase_invoice))
        invoice = frappe.db.get_value("Crane Timesheet", self.name, "sales_invoice")
        if invoice and frappe.db.exists("Sales Invoice", invoice):
            if frappe.db.get_value("Sales Invoice", invoice, "docstatus") != 2:
                frappe.throw(_("Cancel Sales Invoice {0} before cancelling this Timesheet.").format(invoice))

    def on_cancel(self):
        cancel_driver_payroll(self)
