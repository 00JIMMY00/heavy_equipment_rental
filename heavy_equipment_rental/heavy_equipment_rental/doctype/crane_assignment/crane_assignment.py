import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from heavy_equipment_rental.rental_validation import (
    allocation_window,
    allocations,
    booking_conflict,
    check_date_order,
    check_non_negative,
    crane_display_name,
    entry_days,
    lock_cranes,
    recorded_work,
)


@frappe.whitelist()
def get_assignment_defaults(crane=None, rental_rate_unit=None):
    if not (frappe.has_permission("Crane Assignment", "create") or frappe.has_permission("Crane Assignment", "write")):
        frappe.throw(_("You cannot edit Crane Assignments."), frappe.PermissionError)
    settings = frappe.get_single("Heavy Equipment Rental Settings")
    settings.check_permission("read")
    unit = rental_rate_unit or settings.default_selling_uom or "Hour"
    if unit not in ("Hour", "Day", "Month"):
        frappe.throw(_("Select an Hour, Day or Month Rental Rate Unit."))
    result = dict(rental_rate_unit=unit)
    if crane:
        equipment = frappe.get_doc("Crane", crane)
        equipment.check_permission("read")
        result["rental_rate"] = next((r.price for r in equipment.period_prices if r.period == unit), 0)
    return result


class CraneAssignment(Document):
    def validate(self):
        if self.flags.legacy_migration:
            return
        if not self.assigned_cranes:
            frappe.throw(_("Add at least one crane to the assignment."))
        before = self.get_doc_before_save()
        old = {row.name: row for row in before.assigned_cranes} if before else {}
        cranes = {row.crane for row in self.assigned_cranes if row.crane} | {
            row.crane for row in old.values() if row.crane}
        lock_cranes(cranes)
        conditions = dict(frappe.db.sql(
            "SELECT name, operational_condition FROM `tabCrane` WHERE name IN %s FOR UPDATE",
            (tuple(sorted(cranes)),),
        )) if cranes else {}
        if before and (before.customer != self.customer or before.location != self.location):
            if frappe.db.exists("Crane Timesheet", {"assignment": self.name, "docstatus": ["<", 2]}):
                frappe.throw(_("Customer and location cannot change after work has been recorded."))
        others = allocations(cranes, exclude=self.name) if cranes else []
        rows = list(self.assigned_cranes)
        for row in rows:
            if row.name not in old and (not row.rental_rate_unit or not row.rental_rate):
                defaults = get_assignment_defaults(row.crane, row.rental_rate_unit)
                row.rental_rate_unit = row.rental_rate_unit or defaults["rental_rate_unit"]
                if not row.rental_rate:
                    row.rental_rate = defaults.get("rental_rate", 0)
            label = _("Crane {0}, row {1}").format(crane_display_name(row.crane), row.idx)
            check_date_order(row.start_date, row.expected_end_date, label)
            check_non_negative(row.rental_rate, label + " rental rate")
            previous = old.get(row.name)
            if row.rental_rate_unit not in ("Hour", "Day", "Month") or (
                not row.rental_rate and (not previous or previous.rental_rate)
            ):
                frappe.throw(_("{0}: enter a positive agreed Hour, Day or Month rate.").format(label))
            if row.cancelled and (not previous or not previous.cancelled):
                frappe.throw(_("Legacy cancellation flags cannot be edited."))
            if previous and previous.crane != row.crane:
                frappe.throw(_("Change the dates on this row or add a separate crane row."))
            booking_changed = not previous or any(
                str(row.get(field) or "") != str(previous.get(field) or "")
                for field in ("crane", "start_date", "expected_end_date", "cancelled")
            )
            if booking_changed and not row.cancelled and conditions.get(row.crane) == "Inactive":
                frappe.throw(_("{0}: an Inactive crane cannot be booked.").format(label))
            if booking_changed:
                for other in others + rows:
                    if other is row or (other.get("parent") == self.name and other.name == row.name):
                        continue
                    if booking_conflict(row, other):
                        frappe.throw(_("{0}: booking overlaps assignment {1} ({2} to {3}).").format(
                            label, other.get("assignment") or self.name,
                            *(allocation_window(other) or ("", "")),
                        ))
        if before:
            for work in recorded_work(self.name, cranes):
                for day in entry_days(work):
                    if not any(row.crane == work.header_crane and
                               (window := allocation_window(row)) and window[0] <= day <= window[1]
                               for row in rows):
                        frappe.throw(_("Timesheet {0} has work on {1}; keep that crane and date in the assignment.").format(
                            work.timesheet, day))

    def on_trash(self):
        if frappe.db.exists("Crane Timesheet", {"assignment": self.name}):
            frappe.throw(_("Delete or reassign linked Timesheets before deleting this assignment."))
