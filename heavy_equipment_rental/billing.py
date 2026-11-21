"""Draft Sales Invoices for submitted crane work at agreed rental rates."""

from calendar import monthrange
from collections import defaultdict
from decimal import Decimal

import erpnext
import frappe
from frappe import _
from frappe.utils import flt, today

from heavy_equipment_rental.rental_validation import (
	allocation_window,
	interval,
	assignment_doc,
	work_days,
	entered_hour_totals,
)


def _invoice_summaries(assignment, sheets):
	"""Resolve Rental Contract → Timesheet → Sales Invoice links."""
	grouped = defaultdict(list)
	for sheet in sheets:
		if sheet.sales_invoice and frappe.db.exists("Sales Invoice", sheet.sales_invoice):
			grouped[sheet.sales_invoice].append(sheet)
	result = []
	for name, linked_sheets in grouped.items():
		invoice = frappe.get_doc("Sales Invoice", name)
		invoice.check_permission("read")
		item_codes = {row.item_code for row in invoice.items}
		missing_cranes = []
		for sheet in linked_sheets:
			item = frappe.db.get_value("Crane", sheet.crane, "item")
			if not item or item not in item_codes:
				missing_cranes.append(frappe.db.get_value("Crane", sheet.crane, "crane_name") or sheet.crane)
		result.append({
			"name": name,
			"docstatus": invoice.docstatus,
			"grand_total": invoice.grand_total,
			"currency": invoice.currency,
			"timesheets": [sheet.name for sheet in linked_sheets],
			"missing_cranes": sorted(set(missing_cranes)),
			"zero_total": flt(invoice.grand_total) == 0,
		})
	return sorted(result, key=lambda row: row["name"])


def _billing_segments(sheet, bookings):
    """Group submitted shift terms without applying today's prices to historical work."""
    segments = {}
    for entry in sheet.timesheet_entries:
        hours, overtime = flt(entry.worked_hours), flt(entry.overtime_hours)
        if not hours and not overtime:
            continue
        start, end = interval(entry)
        days = set(work_days(start, end))
        matching = [booking for booking in bookings if booking.crane == sheet.crane
                    and (window := allocation_window(booking))
                    and window[0] <= min(days) and max(days) <= window[1]]
        if len(matching) != 1:
            frappe.throw(_("Timesheet {0}, row {1}: work must fit one booked crane period.").format(
                sheet.name, entry.idx))
        row = frappe._dict(matching[0].as_dict())
        for snapshot in (entry, sheet):
            if snapshot.rental_rate_unit:
                row.rental_rate_unit, row.rental_rate = snapshot.rental_rate_unit, snapshot.rental_rate
                break
        else:
            # The oldest hourly shifts stored only Price per Hour. A live booking
            # cannot establish the agreed historical rate when both snapshots are missing.
            row.rental_rate_unit = "Hour"
            row.rental_rate = flt(entry.price_per_hour) if hours else flt(entry.effective_overtime_price)
        if row.rental_rate_unit not in ("Hour", "Day", "Month") or flt(row.rental_rate) <= 0:
            frappe.throw(_("Timesheet {0}, row {1}: a positive submitted rental rate is required. Review this Timesheet before billing.").format(
                sheet.name, entry.idx))
        key = (row.name, row.rental_rate_unit, flt(row.rental_rate))
        if key not in segments:
            segments[key] = frappe._dict(row=row, sheet=sheet, days=set(), regular=[], overtime=defaultdict(list))
        segment = segments[key]
        if hours:
            segment.days.update(days)
            segment.regular.append((start, end, 0, hours))
        if overtime:
            rate = flt(entry.effective_overtime_price)
            segment.overtime[rate].append((start, end, rate, overtime))
    return segments


def _flat_quantity(unit, days):
    if unit == "Day":
        return Decimal(len(days))
    return sum((Decimal(1) / Decimal(monthrange(day.year, day.month)[1]) for day in days), Decimal(0))


def _invoice_line(sheets, allocation, charged_days, regular_hours, overtime_rate=None, overtime_quantity=0):
    unit = "Hour" if overtime_rate is not None else allocation.rental_rate_unit
    quantity = Decimal(str(regular_hours)) if unit == "Hour" else _flat_quantity(unit, charged_days)
    rate = flt(allocation.rental_rate)
    conversion_factor = regular_hours / float(quantity) if quantity else 1
    if overtime_rate is not None:
        quantity, rate, conversion_factor = overtime_quantity, overtime_rate, 1
    if not quantity:
        return []
    crane = frappe.get_doc("Crane", sheets[0].crane, for_update=True)
    if not crane.item:
        crane.ensure_sales_item()
    item = frappe.db.get_value(
        "Item", crane.item, ["is_stock_item", "is_sales_item", "stock_uom", "disabled"], as_dict=True)
    if not item or item.is_stock_item or not item.is_sales_item or item.stock_uom != "Hour" or item.disabled:
        frappe.throw(_("Crane {0}: linked Item must be an enabled non-stock Hour sales service.").format(crane.crane_name))
    return [{
        "crane": crane.name,
        "item_code": crane.item,
        "item_name": crane.crane_name,
        "uom": unit,
        "her_rental_dates": frappe.as_json(sorted(str(day) for day in charged_days)) if charged_days else None,
        "conversion_factor": conversion_factor,
        "qty": float(quantity),
        "rate": rate,
        "description": _("Crane {0}; Rental Contract {1}, row {2}; Timesheets {3}; {4} {5} at {6} per {5}").format(
            crane.crane_name, sheets[0].assignment, allocation.idx,
            ", ".join(sheet.name for sheet in sheets), float(quantity), unit, rate) +
            (" · " + _("Overtime hours") if overtime_rate is not None else ""),
    }]


def _charged_dates(active, segments):
    """Only a live Day/Month invoice line can cover a flat rental date."""
    charged = {}
    overtime_only = set()
    linked = defaultdict(list)
    for sheet_name, invoice in active.items():
        linked[invoice].extend(segments[sheet_name].values())
    legacy = []
    for name, candidates in linked.items():
        invoice = frappe.get_doc("Sales Invoice", name)
        invoice.check_permission("read")
        if invoice.items and all(line.uom == "Hour" for line in invoice.items) and any(part.overtime for part in candidates):
            # A manually edited Hour invoice may still represent regular work.
            # Only repair old links when all its lines reconcile to submitted overtime.
            expected = defaultdict(float)
            actual = defaultdict(float)
            for part in candidates:
                for rate, intervals in part.overtime.items():
                    expected[(part.sheet.crane, rate)] += entered_hour_totals(intervals)[0]
            for line in invoice.items:
                actual[(line.crane, flt(line.rate))] += flt(line.qty)
            if actual.keys() == expected.keys() and all(abs(actual[key] - expected[key]) < 0.000001 for key in actual):
                overtime_only.add(name)
        quantities = defaultdict(float)
        candidate_days = defaultdict(set)
        for line in invoice.items:
            if line.uom not in ("Day", "Month") or flt(line.qty) <= 0:
                continue
            matching = [part for part in candidates if part.row.rental_rate_unit == line.uom and
                        (line.crane == part.sheet.crane if line.crane else line.item_code ==
                         frappe.get_cached_value("Crane", part.sheet.crane, "item"))]
            cranes = {part.sheet.crane for part in matching}
            if not cranes:
                continue
            if len(cranes) != 1:
                frappe.throw(_("Invoice {0}, row {1}: identify the crane on this historical flat rental charge.").format(name, line.idx))
            crane = cranes.pop()
            if line.get("her_rental_dates"):
                dates = {frappe.utils.getdate(day) for day in frappe.parse_json(line.her_rental_dates)}
                if abs(float(_flat_quantity(line.uom, dates)) - flt(line.qty)) > 0.00001:
                    frappe.throw(_("Invoice {0}, row {1}: the edited quantity differs from its billed rental dates. Review the invoice before generating another charge.").format(name, line.idx))
                charged.update({(crane, day): name for day in dates})
            else:
                key = (crane, line.uom)
                quantities[key] += flt(line.qty)
                for part in matching:
                    candidate_days[key].update(part.days)
        for (crane, unit), quantity in quantities.items():
            legacy.append((invoice.creation, name, crane, unit, quantity, candidate_days[(crane, unit)]))
    for _, name, crane, unit, quantity, candidates in sorted(legacy):
        # An older invoice may only have charged the part of a Timesheet that
        # earlier invoices had not covered. Do not guess if its quantities disagree.
        days = {day for day in candidates if (crane, day) not in charged}
        if abs(float(_flat_quantity(unit, days)) - quantity) > 0.00001:
            frappe.throw(_("Review invoice {0}: its {1} quantity does not identify which linked rental dates were billed.").format(name, unit))
        charged.update({(crane, day): name for day in days})
    return charged, overtime_only


def _billing_lines(selected, segments, charged):
    groups = defaultdict(list)
    terms_by_day = {}
    for parts in segments.values():
        for key, part in parts.items():
            for day in part.days:
                day_key = (part.sheet.crane, day)
                prior = terms_by_day.get(day_key)
                if prior and prior != key[1:] and (prior[0] != "Hour" or key[1] != "Hour"):
                    frappe.throw(_("Timesheets for the same crane rental day must use matching billing terms."))
                terms_by_day[day_key] = key[1:]
    for sheet in selected:
        for key, part in segments[sheet.name].items():
            groups[key].append(part)
    lines, overtime_lines, billed, covered = [], [], {}, {}
    for parts in groups.values():
        row = parts[0].row
        new_days = {day for part in parts for day in part.days if (part.sheet.crane, day) not in charged}
        flat_sheets, flat_hours = [], 0
        for part in parts:
            sheet = part.sheet
            regular_hours, _amount = entered_hour_totals(part.regular)
            if row.rental_rate_unit == "Hour" and regular_hours:
                lines.extend(_invoice_line([sheet], row, set(), regular_hours))
                billed[sheet.name] = sheet
            elif part.days & new_days:
                flat_sheets.append(sheet)
                flat_hours += regular_hours
                billed[sheet.name] = sheet
            elif part.days:
                covered[sheet.name] = charged[(sheet.crane, min(part.days))]
            for rate, intervals in part.overtime.items():
                quantity, _amount = entered_hour_totals(intervals)
                overtime_lines.extend(_invoice_line([sheet], row, set(), 0, rate, quantity))
                billed[sheet.name] = sheet
        if flat_sheets:
            lines.extend(_invoice_line(flat_sheets, row, new_days, flat_hours))
    return lines + overtime_lines, list(billed.values()), {key: value for key, value in covered.items() if key not in billed}


def _billing_state(rental, all_sheets, selected):
    names = {sheet.sales_invoice for sheet in all_sheets if sheet.sales_invoice}
    live = set(frappe.get_all("Sales Invoice", filters={"name": ["in", list(names)], "docstatus": ["<", 2]},
                              pluck="name")) if names else set()
    active = {sheet.name: sheet.sales_invoice for sheet in all_sheets if sheet.sales_invoice in live}
    relevant = {sheet.name for sheet in selected} | set(active)
    segments = {sheet.name: _billing_segments(sheet, rental.assigned_cranes)
                for sheet in all_sheets if sheet.name in relevant}
    charged, overtime_only = _charged_dates(active, segments)
    for name, invoice in list(active.items()):
        if invoice not in overtime_only:
            continue
        parts = list(segments[name].values())
        if parts and all(part.row.rental_rate_unit != "Hour" and not part.overtime for part in parts):
            if all((part.sheet.crane, day) not in charged for part in parts for day in part.days):
                del active[name]
    return active, segments, charged


@frappe.whitelist()
def assignment_invoice_summary(assignment):
    rental = assignment_doc(assignment, "read")
    if not frappe.has_permission("Crane Timesheet", "read") or not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw(_("You cannot view Timesheets or Sales Invoices."), frappe.PermissionError)
    sheets = frappe.get_list("Crane Timesheet", filters={"assignment": assignment},
                             fields=["name", "crane", "docstatus", "sales_invoice", "total_crane_billable_hours"],
                             limit_page_length=0)
    submitted = [sheet for sheet in sheets if sheet.docstatus == 1 and flt(sheet.total_crane_billable_hours) > 0]
    linked = [frappe.get_doc("Crane Timesheet", sheet.name) for sheet in submitted if sheet.sales_invoice]
    active, _, _ = _billing_state(rental, linked, [])
    return {
        "invoices": _invoice_summaries(assignment, sheets),
        "submitted_without_invoice": [sheet.name for sheet in submitted if sheet.name not in active],
    }


@frappe.whitelist()
def generate_sales_invoice(assignment=None, timesheet=None, crane=None):
    """Create a draft Sales Invoice directly from submitted crane work."""
    if bool(assignment) == bool(timesheet):
        frappe.throw(_("Choose an Rental Contract or one Timesheet."))
    if not frappe.has_permission("Sales Invoice", "create"):
        frappe.throw(_("You cannot create Sales Invoices."), frappe.PermissionError)
    if timesheet:
        assignment = frappe.db.get_value("Crane Timesheet", timesheet, "assignment")
        if not assignment:
            frappe.throw(_("Crane Timesheet {0} was not found.").format(timesheet))
    rental = assignment_doc(assignment, "read", lock=True)
    names = frappe.db.sql(
        "SELECT name FROM `tabCrane Timesheet` WHERE assignment=%s AND docstatus=1 ORDER BY period_start,name FOR UPDATE",
        assignment, pluck=True)
    all_sheets = [frappe.get_doc("Crane Timesheet", name, for_update=True) for name in names]
    for sheet in all_sheets:
        sheet.check_permission("read")
    selected = [sheet for sheet in all_sheets
                if (not timesheet or sheet.name == timesheet) and (not crane or sheet.crane == crane)]
    if not selected:
        frappe.throw(_("Only submitted Crane Timesheets can be invoiced."))
    active, segments, charged = _billing_state(rental, all_sheets, selected)
    if timesheet and timesheet in active:
        return {"name": active[timesheet], "already_exists": True}
    if timesheet and flt(selected[0].total_crane_billable_hours) <= 0:
        frappe.throw(_("Timesheet {0} has no billable crane hours.").format(timesheet))
    unbilled = [sheet for sheet in selected if sheet.name not in active and flt(sheet.total_crane_billable_hours) > 0]
    if not unbilled:
        if not any(sheet.name in active for sheet in selected):
            return {"no_billable_work": True}
        return {"already_exists": True, "existing_invoices": _invoice_summaries(assignment, selected)}
    frappe.db.savepoint("crane_sales_invoice")
    try:
        for sheet in unbilled:
            if sheet.sales_invoice and frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") == 1:
                if frappe.db.exists("Crane Profit Settlement", {"sales_invoice": sheet.sales_invoice, "docstatus": 1}):
                    frappe.throw(_("Cancel the submitted settlements for invoice {0} before correcting its Timesheet links.").format(sheet.sales_invoice))
        lines, billed, covered = _billing_lines(unbilled, segments, charged)
        company = rental.company or erpnext.get_default_company()
        if lines and not company:
            frappe.throw(_("Set a Company on the Rental Contract or a default Company."))
        invoice = None
        if lines:
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice", "company": company, "customer": rental.customer,
                "posting_date": today(), "due_date": today(),
                "remarks": _("Rental Contract {0}; Location {1}").format(rental.name, rental.location),
                "items": lines,
            })
            invoice.insert()
            for sheet in billed:
                frappe.db.set_value("Crane Timesheet", sheet.name, "sales_invoice", invoice.name,
                                    update_modified=False)
        for name, existing_invoice in covered.items():
            if existing_invoice:
                if frappe.db.exists("Crane Profit Settlement", {"sales_invoice": existing_invoice, "docstatus": 1}):
                    frappe.throw(_("Invoice {0} has settled partner entitlements. Cancel its settlements before adding work.").format(existing_invoice))
                frappe.db.set_value("Crane Timesheet", name, "sales_invoice", existing_invoice,
                                    update_modified=False)
        from heavy_equipment_rental.timesheet_settlement import ensure_settlement

        for sheet in unbilled:
            ensure_settlement(sheet.reload())
    except Exception:
        frappe.db.rollback(save_point="crane_sales_invoice")
        raise
    if invoice:
        return {"name": invoice.name, "timesheets": [sheet.name for sheet in billed]}
    return {"already_exists": True, "existing_invoices": _invoice_summaries(assignment, selected)}


@frappe.whitelist()
def generate_crane_sales_invoices(crane):
    """Create one draft invoice per Rental Contract for this Crane's submitted work."""
    frappe.get_doc("Crane", crane).check_permission("read")
    if not frappe.has_permission("Sales Invoice", "create"):
        frappe.throw(_("You cannot create Sales Invoices."), frappe.PermissionError)
    assignments = frappe.db.sql(
        """SELECT DISTINCT assignment FROM `tabCrane Timesheet`
        WHERE crane=%s AND docstatus=1 AND assignment IS NOT NULL AND total_crane_billable_hours > 0
        ORDER BY assignment""",
        crane, pluck=True,
    )
    invoices = []
    for assignment in assignments:
        result = generate_sales_invoice(assignment=assignment, crane=crane)
        if result.get("name"):
            invoices.append(result["name"])
    return {"invoices": invoices, "submitted_assignments": len(assignments)}
