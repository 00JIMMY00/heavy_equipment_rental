from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from heavy_equipment_rental.fleet_operations import (
	DAY,
	bookings_by_crane,
	column,
	repair_end,
	repairs_in_period,
	report_period,
	visible_fleet,
)


def posted_costs(jobs, details=None):
	"""Use expense debits for parts/services and the final Asset Repair for improvements."""
	costs = {}

	def record(job, doctype, name, amount):
		costs[job] = costs.get(job, 0) + amount
		if details is not None:
			details[job].append(dict(doctype=doctype, name=name, amount=amount))

	by_treatment = defaultdict(list)
	for job in jobs:
		treatment = job.cost_treatment or "Cash Expense"
		by_treatment[treatment].append(job.name)
		if treatment == "No Cost":
			record(job.name, "Crane Maintenance", job.name, 0)
		elif treatment == "Cash Expense" and job.status == "Completed" and job.docstatus == 1:
			source_type, source_name = "Crane Maintenance", job.name
			if details is not None:
				for dt, name in (("Grouped Expense", job.grouped_expense), ("Expense Entry", job.expense_entry)):
					if name and frappe.has_permission(dt, "read", doc=name):
						source_type, source_name = dt, name
						break
			record(job.name, source_type, source_name, flt(job.cost))

	capital = by_treatment["Capitalize Improvement"]
	if capital and frappe.has_permission("Asset Repair", "read"):
		for row in frappe.get_list(
			"Asset Repair",
			filters={"docstatus": 1, "crane_maintenance": ["in", capital]},
			fields=["name", "crane_maintenance", "total_repair_cost"],
			limit_page_length=0,
		):
			record(row.crane_maintenance, "Asset Repair", row.name, flt(row.total_repair_cost))

	if not frappe.has_permission("GL Entry", "read") or not frappe.has_permission("Account", "read"):
		return costs
	sources = {
		"Stock Entry": by_treatment["Operating Expense"],
		"Purchase Invoice": by_treatment["Operating Expense"],
		"Sales Invoice": by_treatment["Recover from Owner"],
	}
	expense_accounts = None
	for doctype, names in sources.items():
		if not names or not frappe.has_permission(doctype, "read"):
			continue
		vouchers = dict(
			frappe.get_list(
				doctype,
				filters={"docstatus": 1, "crane_maintenance": ["in", names]},
				fields=["name", "crane_maintenance"],
				as_list=True,
				limit_page_length=0,
			)
		)
		if not vouchers:
			continue
		if expense_accounts is None:
			expense_accounts = frappe.get_list(
				"Account", filters={"root_type": "Expense", "is_group": 0}, pluck="name", limit_page_length=0
			)
		if expense_accounts:
			for row in frappe.get_list(
				"GL Entry",
				filters={
					"is_cancelled": 0,
					"voucher_type": doctype,
					"voucher_no": ["in", list(vouchers)],
					"account": ["in", expense_accounts],
				},
				fields=["voucher_no", "sum(debit) as debit", "sum(credit) as credit"],
				group_by="voucher_no",
				order_by="voucher_no",
				limit_page_length=0,
			):
				job = vouchers[row.voucher_no]
				record(job, doctype, row.voucher_no, flt(row.debit) - flt(row.credit))
	return costs


def execute(filters=None):
	filters = frappe._dict(filters or {})
	start, end = report_period(filters)
	for source in ("Crane", "Crane Maintenance", "Rental Contract"):
		frappe.has_permission(source, "read", throw=True)
	as_of = getdate()
	names = {r.name: r.crane_name or r.name for r in visible_fleet(filters.crane)}
	jobs = repairs_in_period(names, start, min(end, as_of))
	jobs = [job for job in jobs if repair_end(job, as_of) >= start]
	jobs.sort(
		key=lambda j: (j.status != "In Progress", j.crane, -getdate(j.actual_start_date).toordinal(), j.name)
	)
	bookings = bookings_by_crane(filters.crane, as_of)
	risk_only = filters.view == "Bookings at Risk"
	horizon = as_of + 29 * DAY
	details = defaultdict(list)
	costs = {} if risk_only else posted_costs(jobs, details)
	rows, at_risk, totals = [], set(), defaultdict(float)
	for job in jobs:
		active = job.status == "In Progress"
		upcoming = bookings[job.crane] if active else []
		risks = [b for b in upcoming if b.start_date <= horizon]
		at_risk.update(b.name for b in risks)
		row = dict(
			crane=job.crane,
			crane_name=names[job.crane],
			maintenance=job.name,
			status=_(job.status),
			repair_type=_(job.maintenance_type),
			started=job.actual_start_date,
			ended=None if active else job.actual_end_date,
			repair_days=(repair_end(job, as_of) - getdate(job.actual_start_date)).days + 1,
		)
		if risk_only:
			for booking in risks:
				rows.append(
					dict(
						row,
						contract=booking.parent,
						booking_start=booking.start_date,
						booking_end=booking.expected_end_date,
						customer=booking.customer,
						location=booking.location,
					)
				)
			continue
		currency = (
			frappe.get_cached_value("Company", job.company, "default_currency") if job.company else "EGP"
		)
		next_booking = upcoming[0] if upcoming else None
		rows.append(
			dict(
				row,
				treatment=_(job.cost_treatment or "Cash Expense"),
				currency=currency,
				cost=costs.get(job.name),
				cost_sources=details[job.name],
				risk_sources=[
					dict(doctype="Rental Contract", name=b.parent, day=b.start_date) for b in risks
				],
				risk_count=len(risks),
				contract=next_booking.parent if next_booking else None,
				booking_start=next_booking.start_date if next_booking else None,
			)
		)
		if job.name in costs:
			totals[currency] += costs[job.name]

	columns = [
		column("crane_name", "Crane", "Data", 200),
		column("maintenance", "Crane Maintenance", "Link", 175, "Crane Maintenance"),
		column("status", "Status", "Data", 110),
		column("started", "Actual Start Date", "Date", 160),
		column("repair_days", "Total Repair Days", "Int", 165),
	]
	if risk_only:
		columns.extend(
			[
				column("contract", "Rental Contract", "Link", 145, "Rental Contract"),
				column("booking_start", "Booking Start", "Date", 140),
				column("booking_end", "Booking End", "Date", 125),
				column("customer", "Customer", "Link", 150, "Customer"),
				column("location", "Location", "Link", 145, "Location"),
			]
		)
	else:
		columns.extend(
			[
				column("ended", "Actual End Date", "Date", 160),
				column("risk_count", "Bookings at Risk", "Int", 185),
				column("contract", "Next Booking", "Link", 145, "Rental Contract"),
				column("booking_start", "Booking Start", "Date", 140),
				column("repair_type", "Maintenance Type", "Data", 170),
				column("treatment", "Accounting Treatment", "Data", 195),
				column("cost", "Recorded Repair Cost", "Currency", 195, "currency"),
				column("currency", "Currency", "Link", 110, "Currency"),
			]
		)
	summary = [
		dict(
			label=_("Cranes Under Repair"),
			value=len({j.crane for j in jobs if j.status == "In Progress"}),
			datatype="Int",
			indicator="Orange",
		),
		dict(label=_("Bookings at Risk"), value=len(at_risk), datatype="Int", indicator="Red"),
	]
	summary.extend(
		dict(
			label=_("Recorded Repair Cost"),
			value=amount,
			datatype="Currency",
			currency=currency,
			indicator="Red",
		)
		for currency, amount in sorted(totals.items())
	)
	message = _(
		"Dates select repair history. In-progress repairs flag visible bookings active today or starting in the next 30-day window. "
		"Costs cover the whole repair using visible postings and completed cash repairs. Owner billing revenue is excluded."
	)
	chart = None
	if rows:
		chart = dict(
			type="bar",
			title=_("Maintenance and Downtime"),
			colors=["#db9235", "#df626b"],
			data=dict(
				labels=[_("Cranes Under Repair"), _("Bookings at Risk")],
				datasets=[dict(name=_("Count"), values=[summary[0]["value"], len(at_risk)])],
			),
		)
	if len(totals) == 1:
		currency = next(iter(totals))
		by_treatment = defaultdict(float)
		for row in rows:
			if row["cost"] is not None:
				by_treatment[row["treatment"]] += row["cost"]
		chart = dict(
			type="bar",
			title=_("Recorded Repair Cost"),
			fieldtype="Currency",
			options=currency,
			colors=["#df626b"],
			data=dict(
				labels=list(by_treatment),
				datasets=[dict(name=_("Recorded Repair Cost"), values=list(by_treatment.values()))],
			),
		)
	for currency, amount in sorted(totals.items()):
		rows.append(dict(crane_name=_("Total"), currency=currency, cost=amount, is_total=True))
	return columns, rows, message, chart, summary
