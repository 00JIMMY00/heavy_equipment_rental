"""Draft Sales Invoices for submitted crane work at agreed rental rates."""

from calendar import monthrange
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import erpnext
import frappe
from frappe import _
from frappe.utils import escape_html, flt, getdate, today

from heavy_equipment_rental.rental_validation import (
	allocation_window,
	allocations,
	interval,
	assignment_doc,
	work_days,
)


def _invoice_summaries(assignment, sheets):
	"""Resolve Assignment → Timesheet → Sales Invoice links."""
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


def _invoice_driver_rows(sheets):
    """List company-employed operators without treating each operator as another crane."""
    return [
        {
            "timesheet": sheet.name,
            "employee": employee,
            "timesheet_line_amount": sum(
                Decimal(str(entry.line_amount or 0))
                for entry in sheet.timesheet_entries if entry.employee == employee
            ),
        }
        for sheet in sheets
        for employee in sorted({entry.employee for entry in sheet.timesheet_entries if entry.employee})
    ]


def set_invoice_driver_shares(invoice, method=None):
	"""Allocate the invoice total by the recorded driver line amounts."""
	if not invoice.meta.has_field("customer_pays_drivers_directly") or not invoice.customer_pays_drivers_directly:
		return
	rows = invoice.get("crane_drivers") or []
	weights = [Decimal(str(row.timesheet_line_amount or 0)) for row in rows]
	if not rows or sum(weights) <= 0 or any(weight < 0 for weight in weights):
		frappe.throw(_("Direct driver payment needs linked drivers with positive timesheet line amounts."))
	if any(not row.employee for row in rows):
		frappe.throw(_("Every linked operator needs an Employee before direct payment can be selected."))
	precision = invoice.precision("grand_total") or 2
	quantum = Decimal(1).scaleb(-precision)
	total = Decimal(str(invoice.grand_total or 0)).quantize(quantum, rounding=ROUND_HALF_UP)
	if total <= 0:
		frappe.throw(_("Direct driver payment needs a positive invoice total."))
	positive = [index for index, weight in enumerate(weights) if weight > 0]
	allocated = Decimal(0)
	for index, (row, weight) in enumerate(zip(rows, weights)):
		share = (
			total - allocated if index == positive[-1]
			else (total * weight / sum(weights)).quantize(quantum, rounding=ROUND_HALF_UP)
			if weight > 0 else Decimal(0)
		)
		row.invoice_share = float(share)
		allocated += share


@frappe.whitelist()
def record_direct_driver_payment(invoice_name, payment_date, reference):
	"""Record confirmed customer-to-Employee payment without company bank movement."""
	if not (reference or "").strip():
		frappe.throw(_("Enter the customer payment reference or proof."))
	if not frappe.has_permission("Journal Entry", "create") or not frappe.has_permission("Journal Entry", "submit"):
		frappe.throw(_("Journal Entry create and submit permissions are required."), frappe.PermissionError)
	invoice = frappe.get_doc("Sales Invoice", invoice_name, for_update=True)
	invoice.check_permission("read")
	if invoice.docstatus != 1 or not invoice.customer_pays_drivers_directly:
		frappe.throw(_("Submit a Sales Invoice marked Customer Pays Drivers Directly first."))
	if invoice.driver_direct_payment_journal_entry:
		frappe.throw(_("Direct driver payment has already been recorded on Journal Entry {0}.").format(invoice.driver_direct_payment_journal_entry))
	date = getdate(payment_date)
	if date < getdate(invoice.posting_date) or date > getdate(today()):
		frappe.throw(_("Payment date must be between invoice posting date and today."))
	if flt(invoice.outstanding_amount, 2) != flt(invoice.grand_total, 2) or flt(invoice.paid_amount, 2):
		frappe.throw(_("The full invoice must still be unpaid to record direct driver payment."))
	company_currency = frappe.db.get_value("Company", invoice.company, "default_currency")
	if invoice.currency != company_currency or flt(invoice.conversion_rate, 6) != 1:
		frappe.throw(_("Direct driver payment currently requires the invoice and company to use the same currency."))
	settings = frappe.get_single("Heavy Equipment Rental Settings")
	expense_account = settings.driver_payment_expense_account
	payable_account = settings.driver_payment_payable_account
	for account, root_type, account_type in (
		(expense_account, "Expense", None),
		(payable_account, "Liability", "Payable"),
		(invoice.debit_to, "Asset", "Receivable"),
	):
		data = frappe.db.get_value("Account", account, ["company", "root_type", "account_type", "is_group"], as_dict=True) if account else None
		if not data or data.company != invoice.company or data.is_group or data.root_type != root_type or (account_type and data.account_type != account_type):
			frappe.throw(_("Configure valid company expense and Employee payable accounts before recording direct driver payment."))
	set_invoice_driver_shares(invoice)
	shares = defaultdict(Decimal)
	for row in invoice.crane_drivers:
		if row.invoice_share:
			if frappe.db.get_value("Employee", row.employee, "company") != invoice.company:
				frappe.throw(_("Driver Employee {0} must belong to the invoice company.").format(row.employee))
			shares[row.employee] += Decimal(str(row.invoice_share))
	if not shares:
		frappe.throw(_("No payable driver shares were found."))
	accounts = []
	for employee, share in sorted(shares.items()):
		accounts.extend([
			{"account": expense_account, "debit_in_account_currency": float(share)},
			{"account": payable_account, "party_type": "Employee", "party": employee, "credit_in_account_currency": float(share)},
			{"account": payable_account, "party_type": "Employee", "party": employee, "debit_in_account_currency": float(share)},
		])
	accounts.append({
		"account": invoice.debit_to,
		"party_type": "Customer",
		"party": invoice.customer,
		"reference_type": "Sales Invoice",
		"reference_name": invoice.name,
		"credit_in_account_currency": invoice.grand_total,
	})
	frappe.db.savepoint("direct_driver_payment")
	try:
		journal = frappe.get_doc({
			"doctype": "Journal Entry",
			"company": invoice.company,
			"posting_date": date,
			"user_remark": _("Customer paid Crane Drivers directly for Sales Invoice {0}. Reference: {1}").format(invoice.name, reference.strip()),
			"accounts": accounts,
		})
		journal.insert()
		journal.submit()
		invoice.db_set("driver_direct_payment_journal_entry", journal.name)
		invoice.add_comment("Info", _("Direct driver payment recorded on Journal Entry {0}. Reference: {1}").format(journal.name, escape_html(reference.strip())))
	except Exception:
		frappe.db.rollback(save_point="direct_driver_payment")
		raise
	return {"journal_entry": journal.name}


def guard_direct_driver_payment_cancel(invoice, method=None):
	if invoice.meta.has_field("driver_direct_payment_journal_entry") and invoice.driver_direct_payment_journal_entry:
		if frappe.db.get_value("Journal Entry", invoice.driver_direct_payment_journal_entry, "docstatus") == 1:
			frappe.throw(_("Cancel direct driver payment Journal Entry {0} before cancelling this invoice.").format(
				invoice.driver_direct_payment_journal_entry
			))


def clear_direct_driver_payment_link(journal, method=None):
	for invoice in frappe.get_all(
		"Sales Invoice", filters={"driver_direct_payment_journal_entry": journal.name}, pluck="name"
	):
		frappe.db.set_value("Sales Invoice", invoice, "driver_direct_payment_journal_entry", None, update_modified=False)


def _work_days(sheet):
    return {day for entry in sheet.timesheet_entries for day in work_days(*interval(entry))}


def _rental_allocation(sheet, days):
    matching = [row for row in allocations([sheet.crane], assignment=sheet.assignment)
                if (window := allocation_window(row)) and
                all(window[0] <= day <= window[1] for day in days)]
    if len(matching) != 1:
        frappe.throw(_("Timesheet {0}: work must fit one crane period on its Assignment.").format(sheet.name))
    row = matching[0]
    if row.rental_rate_unit not in ("Hour", "Day", "Month") or flt(row.rental_rate) <= 0:
        frappe.throw(_("Assignment {0}, row {1}: set a positive agreed rental rate.").format(
            sheet.assignment, row.idx))
    if flt(sheet.total_crane_billable_hours) <= 0:
        frappe.throw(_("Timesheet {0} has no billable crane hours.").format(sheet.name))
    return row


def _invoice_line(sheets, allocation, charged_days):
    unit = allocation.rental_rate_unit
    quantity = (
        sum(Decimal(str(sheet.total_crane_billable_hours)) for sheet in sheets)
        if unit == "Hour" else Decimal(len(charged_days))
        if unit == "Day" else sum(
            (Decimal(1) / Decimal(monthrange(day.year, day.month)[1]) for day in charged_days),
            Decimal(0),
        )
    )
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
        "uom": item.stock_uom,
        "qty": float(quantity) if unit == "Hour" else 1,
        "rate": flt(allocation.rental_rate) if unit == "Hour" else float(quantity * Decimal(str(allocation.rental_rate))),
        "description": _("Crane {0}; Assignment {1}, row {2}; Timesheets {3}; {4} {5} at {6} per {5}").format(
            crane.crane_name, sheets[0].assignment, allocation.idx,
            ", ".join(sheet.name for sheet in sheets), float(quantity), unit, allocation.rental_rate),
    }]


def _billing_lines(selected, all_sheets, active_invoices):
    """Charge each submitted crane hour or rental day once per agreed crane period."""
    charged = {}
    for sheet in all_sheets:
        if sheet.name in active_invoices:
            row = _rental_allocation(sheet, _work_days(sheet))
            charged.update({(row.name, day): active_invoices[sheet.name] for day in _work_days(sheet)})
    groups = defaultdict(list)
    for sheet in selected:
        days = _work_days(sheet)
        row = _rental_allocation(sheet, days)
        groups[row.name].append((sheet, row, days))
    lines, billed, covered = [], [], {}
    for group in groups.values():
        row = group[0][1]
        if row.rental_rate_unit == "Hour":
            for sheet, _, _ in group:
                lines.extend(_invoice_line([sheet], row, set()))
                billed.append(sheet)
            continue
        new_days = set().union(*(days for _, _, days in group)) - {
            day for key, day in charged if key == row.name
        }
        if new_days:
            sheets = [sheet for sheet, _, days in group if days & new_days]
            lines.extend(_invoice_line(sheets, row, new_days))
            billed.extend(sheets)
        for sheet, _, days in group:
            if not days & new_days:
                covered[sheet.name] = next(
                    (charged[(row.name, day)] for day in sorted(days)
                     if (row.name, day) in charged), None)
    return lines, billed, covered


@frappe.whitelist()
def assignment_invoice_summary(assignment):
    assignment_doc(assignment, "read")
    if not frappe.has_permission("Crane Timesheet", "read") or not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw(_("You cannot view Timesheets or Sales Invoices."), frappe.PermissionError)
    sheets = frappe.get_list("Crane Timesheet", filters={"assignment": assignment},
                             fields=["name", "crane", "docstatus", "sales_invoice"], limit_page_length=0)
    return {
        "invoices": _invoice_summaries(assignment, sheets),
        "submitted_without_invoice": [sheet.name for sheet in sheets if sheet.docstatus == 1 and (
            not sheet.sales_invoice or not frappe.db.exists("Sales Invoice", sheet.sales_invoice) or
            frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") == 2)],
    }


@frappe.whitelist()
def generate_sales_invoice(assignment=None, timesheet=None, crane=None):
    """Create a draft Sales Invoice directly from submitted crane work."""
    if bool(assignment) == bool(timesheet):
        frappe.throw(_("Choose an Assignment or one Timesheet."))
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
    active = {sheet.name: sheet.sales_invoice for sheet in all_sheets
              if sheet.sales_invoice and frappe.db.exists("Sales Invoice", sheet.sales_invoice) and
              frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") != 2}
    if timesheet and timesheet in active:
        return {"name": active[timesheet], "already_exists": True}
    unbilled = [sheet for sheet in selected if sheet.name not in active]
    if not unbilled:
        return {"already_exists": True, "existing_invoices": _invoice_summaries(assignment, selected)}
    frappe.db.savepoint("crane_sales_invoice")
    try:
        lines, billed, covered = _billing_lines(unbilled, all_sheets, active)
        company = rental.company or erpnext.get_default_company()
        if lines and not company:
            frappe.throw(_("Set a Company on the Assignment or a default Company."))
        invoice = None
        if lines:
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice", "company": company, "customer": rental.customer,
                "posting_date": today(), "due_date": today(),
                "remarks": _("Crane Assignment {0}; Location {1}").format(rental.name, rental.location),
                "items": lines, "crane_drivers": _invoice_driver_rows(billed),
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
    """Create one draft invoice per Assignment for this Crane's submitted work."""
    frappe.get_doc("Crane", crane).check_permission("read")
    if not frappe.has_permission("Sales Invoice", "create"):
        frappe.throw(_("You cannot create Sales Invoices."), frappe.PermissionError)
    assignments = frappe.db.sql(
        """SELECT DISTINCT assignment FROM `tabCrane Timesheet`
        WHERE crane=%s AND docstatus=1 AND assignment IS NOT NULL
        ORDER BY assignment""",
        crane, pluck=True,
    )
    invoices = []
    for assignment in assignments:
        result = generate_sales_invoice(assignment=assignment, crane=crane)
        if result.get("name"):
            invoices.append(result["name"])
    return {"invoices": invoices, "submitted_assignments": len(assignments)}
