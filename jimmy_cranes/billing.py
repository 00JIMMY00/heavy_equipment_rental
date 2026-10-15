"""Draft Sales Invoices for submitted crane work at agreed rental rates."""

from calendar import monthrange
from collections import defaultdict
from decimal import Decimal

import erpnext
import frappe
from frappe import _
from frappe.utils import escape_html, flt, today

from jimmy_cranes.rental_validation import (
	allocation_window,
	allocations,
	interval,
	project_doc,
	work_days,
)


def _invoice_summaries(project, sheets):
	"""Resolve Project → Timesheet → Sales Invoice links, including edited drafts."""
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


def _billing_lines(selected, all_sheets, active_invoices):
	"""Build charge lines and distinguish days already covered by another invoice."""
	charged_by_day = {}
	for sheet in all_sheets:
		if sheet.name in active_invoices:
			for day in _work_days(sheet):
				charged_by_day.setdefault((sheet.crane, day), active_invoices[sheet.name])
	groups = defaultdict(list)
	for sheet in selected:
		days = _work_days(sheet)
		row = _rental_allocation(sheet, days)
		groups[row.name].append((sheet, row, days))

	lines, invoice_sheets, covered_links = [], [], {}
	for group in groups.values():
		row = group[0][1]
		if row.rental_rate_unit == "Hour":
			for sheet, allocation_row, days in group:
				lines.append(_invoice_line([sheet], row, set()))
				invoice_sheets.append(sheet)
			continue
		new_days = set().union(*(days for sheet, allocation_row, days in group)) - {
			day for (crane, day) in charged_by_day if crane == group[0][0].crane
		}
		if new_days:
			sheets = [sheet for sheet, allocation_row, days in group if days & new_days]
			lines.append(_invoice_line(sheets, row, new_days))
			invoice_sheets.extend(sheets)
		for sheet, allocation_row, days in group:
			if not days & new_days:
				covered_links[sheet.name] = next(
					charged_by_day[(sheet.crane, day)]
					for day in sorted(days)
					if (sheet.crane, day) in charged_by_day
				)
	return lines, invoice_sheets, covered_links


@frappe.whitelist()
def project_invoice_summary(project):
	"""Read-only invoice overview for a Crane Project form."""
	project_doc(project, "read")
	if not frappe.has_permission("Crane Timesheet", "read") or not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("You cannot view Crane Timesheets or Sales Invoices."), frappe.PermissionError)
	sheets = frappe.get_list(
		"Crane Timesheet", filters={"project": project},
		fields=["name", "crane", "docstatus", "sales_invoice"], limit_page_length=0,
	)
	return {
		"invoices": _invoice_summaries(project, sheets),
		"submitted_without_invoice": [
			sheet.name for sheet in sheets
			if sheet.docstatus == 1 and (
				not sheet.sales_invoice
				or not frappe.db.exists("Sales Invoice", sheet.sales_invoice)
				or frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") == 2
			)
		],
	}


@frappe.whitelist()
def rebuild_draft_invoice(project, invoice_name, reason):
	"""Explicitly replace a draft's items from its linked submitted timesheets."""
	if not (reason or "").strip():
		frappe.throw(_("Enter a reason for rebuilding the draft invoice."))
	crane_project = project_doc(project, "read", lock=True)
	invoice = frappe.get_doc("Sales Invoice", invoice_name, for_update=True)
	invoice.check_permission("write")
	if invoice.docstatus != 0:
		frappe.throw(_("Only draft Sales Invoices can be rebuilt."))
	if invoice.customer != crane_project.customer or (crane_project.company and invoice.company != crane_project.company):
		frappe.throw(_("Invoice customer or company does not match the Crane Project."))
	if frappe.db.sql(
		"SELECT name FROM `tabCrane Timesheet` WHERE sales_invoice=%s AND project!=%s LIMIT 1",
		(invoice_name, project),
	):
		frappe.throw(_("This Sales Invoice also links to another Crane Project."))
	names = frappe.db.sql(
		"SELECT name FROM `tabCrane Timesheet` WHERE project=%s AND docstatus=1 ORDER BY period_start, name FOR UPDATE",
		project, pluck=True,
	)
	all_sheets = [frappe.get_doc("Crane Timesheet", name, for_update=True) for name in names]
	for sheet in all_sheets:
		sheet.check_permission("read")
	selected = [sheet for sheet in all_sheets if sheet.sales_invoice == invoice_name]
	if not selected:
		frappe.throw(_("No submitted Crane Timesheets are linked to this Sales Invoice."))
	active = {}
	for sheet in all_sheets:
		if sheet.sales_invoice and sheet.sales_invoice != invoice_name and frappe.db.exists("Sales Invoice", sheet.sales_invoice):
			if frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") != 2:
				active[sheet.name] = sheet.sales_invoice
	frappe.db.savepoint("rebuild_crane_invoice")
	try:
		lines, billed_sheets, covered_links = _billing_lines(selected, all_sheets, active)
		if not lines or covered_links:
			frappe.throw(_("This draft contains days already covered by another invoice. Review the linked timesheets before rebuilding."))
		invoice.set("items", lines)
		invoice.save()
		invoice.add_comment(
			"Info",
			_("Crane rental items rebuilt from Timesheets {0} by {1}. Reason: {2}").format(
				", ".join(escape_html(sheet.name) for sheet in selected),
				escape_html(frappe.session.user), escape_html(reason.strip()),
			),
		)
	except frappe.QueryDeadlockError:
		raise
	except Exception:
		frappe.db.rollback(save_point="rebuild_crane_invoice")
		raise
	return {"name": invoice.name, "grand_total": invoice.grand_total}


def _work_days(sheet):
	return {day for entry in sheet.timesheet_entries for day in work_days(*interval(entry))}


def _rental_allocation(sheet, days):
	matching = [
		row
		for row in allocations([sheet.crane], sheet.project)
		if (window := allocation_window(row))
		and all(window[0] <= day <= window[1] for day in days)
	]
	if len(matching) != 1:
		frappe.throw(
			_("Timesheet {0}: work must fit one Reserved crane allocation with an agreed rental rate.").format(sheet.name)
		)
	row = matching[0]
	if row.rental_rate_unit not in ("Hour", "Day", "Month") or (
		row.rental_rate_unit != "Hour" and not flt(row.rental_rate)
	):
		frappe.throw(
			_("Timesheet {0}: set a positive Day or Month rental rate on assignment {1}, row {2}.").format(
				sheet.name, row.assignment, row.idx
			)
		)
	if flt(sheet.total_crane_billable_hours) <= 0:
		frappe.throw(_("Timesheet {0} has no billable crane hours.").format(sheet.name))
	if row.rental_rate_unit == "Hour" and flt(sheet.total_amount) <= 0:
		frappe.throw(_("Timesheet {0} has no positive hourly price.").format(sheet.name))
	return row


def _invoice_line(sheets, allocation, charged_days):
	unit = allocation.rental_rate_unit
	hours = sum((Decimal(str(sheet.total_crane_billable_hours)) for sheet in sheets), Decimal(0))
	quantity = (
		hours
		if unit == "Hour"
		else Decimal(len(charged_days))
		if unit == "Day"
		else sum(
			(Decimal(1) / Decimal(monthrange(day.year, day.month)[1]) for day in charged_days),
			Decimal(0),
		)
	)
	amount = Decimal(str(sheets[0].total_amount)) if unit == "Hour" else quantity * Decimal(str(allocation.rental_rate))
	hourly_rates = {Decimal(str(entry.price_per_hour)) for entry in sheets[0].timesheet_entries} if unit == "Hour" else set()
	hourly_rate = next(iter(hourly_rates)) if len(hourly_rates) == 1 else None
	crane = frappe.get_doc("Crane", sheets[0].crane, for_update=True)
	if not crane.item:
		crane.ensure_sales_item()
	item = frappe.db.get_value(
		"Item", crane.item, ["is_stock_item", "is_sales_item", "stock_uom", "disabled"], as_dict=True
	)
	if not item or item.is_stock_item or not item.is_sales_item or item.stock_uom != "Hour" or item.disabled:
		frappe.throw(_("Crane {0}: linked Item must be an enabled, sellable, non-stock Hour service.").format(crane.crane_name))
	return {
		"item_code": crane.item,
		"item_name": crane.crane_name,
		"uom": "Hour",
		# ERPNext rounds a line's rate before multiplying. Use one service
		# charge when hourly rates vary, or for daily and monthly amounts.
		"qty": float(hours) if unit == "Hour" and hourly_rate is not None else 1,
		"rate": float(hourly_rate) if unit == "Hour" and hourly_rate is not None else float(amount),
		"description": (
			_("Crane {0}; Timesheet {1}; assignment {2}, row {3}; {4} billable hours at varying hourly prices").format(
				crane.crane_name, sheets[0].name, allocation.assignment, allocation.idx, float(hours)
			)
			if unit == "Hour" and hourly_rate is None
			else _("Crane {0}; Timesheets {1}; assignment {2}, row {3}; {4} {5} at {6} per {7}").format(
				crane.crane_name,
				", ".join(sheet.name for sheet in sheets),
				allocation.assignment,
				allocation.idx,
				float(quantity),
				unit if quantity == 1 else unit + "s",
				hourly_rate if unit == "Hour" else allocation.rental_rate,
				unit,
			)
		),
	}


@frappe.whitelist()
def generate_sales_invoice(project=None, timesheet=None):
	"""Create a draft invoice; daily/monthly crane-days are charged only once."""
	if bool(project) == bool(timesheet):
		frappe.throw(_("Choose either a Crane Project or one Crane Timesheet."))
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("You cannot create Sales Invoices."), frappe.PermissionError)
	if timesheet:
		project = frappe.db.get_value("Crane Timesheet", timesheet, "project")
		if not project:
			frappe.throw(_("Crane Timesheet {0} was not found.").format(timesheet))
	crane_project = project_doc(project, "read", lock=True)
	names = frappe.db.sql(
		"SELECT name FROM `tabCrane Timesheet` WHERE project=%s AND docstatus=1 ORDER BY period_start, name FOR UPDATE",
		project,
		pluck=True,
	)
	all_sheets = [frappe.get_doc("Crane Timesheet", name, for_update=True) for name in names]
	for sheet in all_sheets:
		sheet.check_permission("read")
	if timesheet:
		selected = [sheet for sheet in all_sheets if sheet.name == timesheet]
		if not selected:
			frappe.throw(_("Only submitted Crane Timesheets can be invoiced."))
	else:
		selected = all_sheets

	active_invoices = {}
	for sheet in all_sheets:
		if sheet.sales_invoice and frappe.db.exists("Sales Invoice", sheet.sales_invoice):
			if frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") != 2:
				active_invoices[sheet.name] = sheet.sales_invoice
	if timesheet and timesheet in active_invoices:
		return {"name": active_invoices[timesheet], "already_exists": True}
	unbilled = [sheet for sheet in selected if sheet.name not in active_invoices]
	if not unbilled:
		if not selected:
			frappe.throw(_("No submitted Crane Timesheets were found for this Crane Project."))
		return {
			"already_exists": True,
			"existing_invoices": _invoice_summaries(project, selected),
		}

	frappe.db.savepoint("crane_sales_invoice")
	try:
		lines, invoice_sheets, covered_links = _billing_lines(unbilled, all_sheets, active_invoices)
		company = crane_project.company or erpnext.get_default_company()
		if lines and not company:
			frappe.throw(_("Set a Company on the Crane Project or a default Company for this user."))
		invoice = None
		if lines:
			invoice = frappe.get_doc({
				"doctype": "Sales Invoice",
				"company": company,
				"customer": crane_project.customer,
				"posting_date": today(),
				"due_date": today(),
				"remarks": _("Crane Project {0}").format(crane_project.name),
				"items": lines,
			})
			invoice.insert()
			for sheet in invoice_sheets:
				frappe.db.set_value("Crane Timesheet", sheet.name, "sales_invoice", invoice.name, update_modified=False)
		for sheet_name, invoice_name in covered_links.items():
			frappe.db.set_value("Crane Timesheet", sheet_name, "sales_invoice", invoice_name, update_modified=False)
	except frappe.QueryDeadlockError:
		raise
	except Exception:
		frappe.db.rollback(save_point="crane_sales_invoice")
		raise
	if invoice:
		return {"name": invoice.name, "timesheets": [sheet.name for sheet in invoice_sheets]}
	return {"name": next(iter(covered_links.values())), "already_exists": True}
