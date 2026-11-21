"""Operational repair jobs coordinate native stock, invoices and asset accounting.

No shadow stock balance, asset ledger or second expense is created here.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.rental_validation import lock_cranes


DOCUMENTS = ("Stock Entry", "Purchase Invoice", "Sales Invoice", "Asset Repair")
ALLOWED = {
	"Operating Expense": ("Stock Entry", "Purchase Invoice"),
	"Capitalize Improvement": ("Asset Repair", "Purchase Invoice"),
	"Recover from Owner": ("Sales Invoice",),
}


def install_fields():
	create_custom_fields({doctype: [
		dict(fieldname="crane_maintenance", fieldtype="Link", label="Crane Maintenance",
			options="Crane Maintenance", insert_after="company", no_copy=0, in_standard_filter=1),
		dict(fieldname="crane", fieldtype="Link", label="Crane", options="Crane",
			insert_after="crane_maintenance", read_only=1, in_standard_filter=1),
	] for doctype in DOCUMENTS})


def documents(maintenance, *, check_permissions=True):
	result = []
	for doctype in DOCUMENTS:
		for row in frappe.get_all(doctype, filters={"crane_maintenance": maintenance},
			fields=["name", "docstatus"], order_by="creation"):
			if check_permissions:
				frappe.get_doc(doctype, row.name).check_permission("read")
			result.append(dict(doctype=doctype, **row))
	return result


@frappe.whitelist()
def repair_documents(maintenance):
	frappe.get_doc("Crane Maintenance", maintenance).check_permission("read")
	return documents(maintenance)


def validate_maintenance(doc, *, require_postings=False):
	before = doc.get_doc_before_save()
	rows = documents(doc.name, check_permissions=False) if not doc.is_new() else []
	if before and not require_postings and any(r["docstatus"] != 2 for r in rows) and any(
		str(doc.get(field) or "") != str(before.get(field) or "") and not (
			field == "actual_end_date" and not before.actual_end_date and doc.status == "Completed"
		) for field in ("crane", "company", "cost_treatment",
			"crane_assignment", "crane_timesheet", "actual_start_date", "actual_end_date", "owner_customer")
	):
		frappe.throw(_("Repair accounting documents already exist. Cancel/delete them before changing the job's financial attribution."))
	if doc.status == "Cancelled" and any(r["docstatus"] != 2 for r in rows):
		frappe.throw(_("Cancel/delete the repair accounting documents before cancelling maintenance."))
	if doc.cost_treatment == "Cash Expense":
		return
	if doc.grouped_expense or doc.expense_entry or flt(doc.cost):
		frappe.throw(_("Native repair documents record the costs. Clear Cash Expense Cost; do not post the same repair twice."))
	crane = frappe.get_doc("Crane", doc.crane)
	crane.check_permission("read")
	company = crane.sharing_company or (frappe.get_cached_value("Asset", crane.asset, "company") if crane.asset else None)
	doc.company = doc.company or company
	if not doc.company:
		frappe.throw(_("Select the Company responsible for this repair."))
	frappe.get_doc("Company", doc.company).check_permission("read")
	if company and doc.company != company:
		frappe.throw(_("Repair Company must match the Crane's Asset/agreement Company."))
	if doc.cost_treatment == "Capitalize Improvement":
		if not doc.capitalization_reason:
			frappe.throw(_("Explain the future benefit or major replacement that justifies capitalization."))
		capital_asset(crane, doc.company)
	if doc.cost_treatment == "Recover from Owner" and not doc.owner_customer:
		frappe.throw(_("Select the owner Customer to invoice for this repair."))
	if doc.status == "Completed" and (require_postings or not (getattr(doc, "_action", None) == "submit" and doc.repair_source not in (None, "", "Manual Documents"))):
		active = [r for r in rows if r["docstatus"] != 2]
		if any(r["docstatus"] == 0 for r in active):
			frappe.throw(_("Submit or delete draft repair accounting documents before completing maintenance."))
		required = {"Operating Expense": ("Stock Entry", "Purchase Invoice"),
			"Capitalize Improvement": ("Asset Repair",), "Recover from Owner": ("Sales Invoice",)}.get(doc.cost_treatment)
		if required and not any(r["doctype"] in required and r["docstatus"] == 1 for r in active):
			frappe.throw(_("Post the repair's native accounting document before completing maintenance."))


def capital_asset(crane, company):
	from heavy_equipment_rental.crane_assets import accounting_basis
	if not crane.asset:
		frappe.throw(_("Link the reviewed native Asset on the Crane before capitalizing improvements."))
	asset = frappe.get_doc("Asset", crane.asset)
	asset.check_permission("read")
	if (not accounting_basis(crane) or
		asset.asset_owner != "Company" or (asset.asset_owner_company or asset.company) != company or
		asset.company != company or asset.docstatus != 1):
		frappe.throw(_("Only a submitted Asset recognized in this Company's books can receive capital improvements."))
	if crane.asset_accounting_basis == "Company Interest Only":
		# Invoice/stock costs must represent the recognized interest only; never
		# multiply partner percentages against a value already reduced to our share.
		frappe.msgprint(_("Record only this Company's recognized improvement cost. Other owners' costs require separate recovery/funding documents."), alert=True)
	return asset


@frappe.whitelist()
def make_repair_document(maintenance, doctype):
	job = frappe.get_doc("Crane Maintenance", maintenance)
	job.check_permission("write")
	if job.docstatus != 0 and frappe.flags.maintenance_posting != job.name:
		frappe.throw(_("Cancel and amend Maintenance before creating new repair documents."))
	if job.status == "Cancelled" or doctype not in ALLOWED.get(job.cost_treatment, ()):
		frappe.throw(_("This document is not appropriate for the repair's Cost Treatment."))
	frappe.has_permission(doctype, "create", throw=True)
	crane = frappe.get_doc("Crane", job.crane)
	crane.check_permission("read")
	doc = frappe.new_doc(doctype)
	doc.update(dict(company=job.company, crane=job.crane, crane_maintenance=job.name))
	if doctype == "Stock Entry":
		doc.update(dict(stock_entry_type="Material Issue", purpose="Material Issue",
			posting_date=job.actual_end_date or today(), set_posting_time=1))
	elif doctype == "Asset Repair":
		asset = capital_asset(crane, job.company)
		doc.update(dict(asset=asset.name, failure_date=job.actual_start_date or today(),
			completion_date=job.actual_end_date or today(), repair_status="Completed",
			capitalize_repair_cost=1, cost_center=asset.cost_center,
			description=job.description, actions_performed=job.capitalization_reason))
	else:
		doc.posting_date = job.actual_end_date or today()
		if doctype == "Purchase Invoice":
			doc.update_stock = 0
		if doctype == "Sales Invoice":
			doc.update(dict(customer=job.owner_customer, update_stock=1,
				remarks=_("Repair of Crane {0}; job {1}").format(job.crane, job.name)))
	return doc.as_dict()


def validate_native_document(doc, method=None):
	"""Never trust client-supplied attribution or mix cost treatments."""
	before = doc.get_doc_before_save()
	if before and before.get("crane_maintenance") and before.crane_maintenance != doc.get("crane_maintenance"):
		frappe.throw(_("A repair document cannot be detached from its maintenance job."))
	if not doc.get("crane_maintenance") and doc.doctype == "Asset Repair" and (doc.stock_consumption or doc.capitalize_repair_cost):
		if frappe.db.exists("Crane", {"asset": doc.asset}):
			frappe.throw(_("Create the repair from Crane Maintenance to classify its costs before posting."))
	if not doc.get("crane_maintenance"):
		if doc.doctype == "Stock Entry" and doc.get("asset_repair"):
			repair = frappe.get_doc("Asset Repair", doc.asset_repair)
			if repair.get("crane_maintenance"):
				doc.crane_maintenance, doc.crane = repair.crane_maintenance, repair.crane
			else:
				return
		else:
			if doc.doctype == "Stock Entry" and doc.get("crane"):
				frappe.throw(_("Select Crane Maintenance to attribute repair stock consumption."))
			return
	job = frappe.get_doc("Crane Maintenance", doc.crane_maintenance, for_update=True)
	job.check_permission("read")
	if doc.is_new() and job.docstatus != 0 and frappe.flags.maintenance_posting != job.name:
		frappe.throw(_("Cancel and amend Maintenance before adding repair documents."))
	internal_capital_issue = doc.doctype == "Stock Entry" and doc.get("asset_repair") and job.cost_treatment == "Capitalize Improvement"
	if job.status == "Cancelled" or (doc.doctype not in ALLOWED.get(job.cost_treatment, ()) and not internal_capital_issue):
		frappe.throw(_("Document and maintenance Cost Treatment do not agree."))
	if doc.company != job.company:
		frappe.throw(_("Repair document and maintenance must use the same Company."))
	if doc.get("crane") and doc.crane != job.crane:
		frappe.throw(_("Repair document Crane does not match maintenance."))
	doc.crane = job.crane
	before = doc.get_doc_before_save()
	if before and before.get("crane_maintenance") != doc.crane_maintenance and before.get("crane_maintenance"):
		frappe.throw(_("A repair document cannot be moved to a different maintenance job."))
	if doc.doctype == "Stock Entry":
		if doc.purpose != "Material Issue":
			frappe.throw(_("Use Material Issue for repair consumption."))
		if not frappe.get_cached_value("Company", doc.company, "enable_perpetual_inventory"):
			frappe.throw(_("Repair stock accounting requires perpetual inventory for this Company."))
		for row in doc.items:
			if row.expense_account and frappe.get_cached_value("Account", row.expense_account, "root_type") != "Expense":
				frappe.throw(_("Repair stock issues must use an Expense account. Asset Repair handles capitalization separately."))
	elif doc.doctype == "Sales Invoice":
		if doc.customer != job.owner_customer:
			frappe.throw(_("Invoice the owner Customer selected on maintenance."))
		if any(frappe.get_cached_value("Item", row.item_code, "is_stock_item") for row in doc.items) and not doc.update_stock:
			frappe.throw(_("Enable Update Stock to consume the repair parts exactly once."))
	elif doc.doctype == "Purchase Invoice":
		stock_purchase = job.cost_treatment in ("Operating Expense", "Capitalize Improvement") and job.get("repair_source") in ("External Parts", "Supplier Bill")
		if stock_purchase:
			if doc.is_return or any(r.is_fixed_asset for r in doc.items) or bool(doc.update_stock) != any(frappe.get_cached_value("Item", r.item_code, "is_stock_item") for r in doc.items):
				frappe.throw(_("Supplier bills must update stock when they contain stock parts and cannot contain fixed-asset items or returns."))
		if not stock_purchase and doc.is_return and doc.return_against and frappe.db.exists("Asset Repair", {"purchase_invoice": doc.return_against, "docstatus": 1}):
			frappe.throw(_("Cancel the Asset Repair before returning its capitalized service invoice."))
		if not stock_purchase and (doc.update_stock or any(row.is_fixed_asset or frappe.get_cached_value("Item", row.item_code, "is_stock_item") for row in doc.items)):
			frappe.throw(_("Repair Purchase Invoices are for external services. Purchase spare parts into stock separately, then consume them on the repair."))
		if any(frappe.get_cached_value("Account", row.expense_account, "root_type") != "Expense" for row in doc.items if not frappe.get_cached_value("Item", row.item_code, "is_stock_item")):
			frappe.throw(_("Repair service invoices must post to Expense accounts; Asset Repair reclassifies qualifying improvements."))
	elif doc.doctype == "Asset Repair":
		crane = frappe.get_doc("Crane", job.crane)
		asset = capital_asset(crane, doc.company)
		if doc.asset != asset.name or not doc.capitalize_repair_cost:
			frappe.throw(_("Use the Crane's Asset and enable Capitalize Repair Cost for an improvement. Routine stock repairs use Material Issue."))
		if doc.purchase_invoice:
			invoice = frappe.get_doc("Purchase Invoice", doc.purchase_invoice)
			invoice.check_permission("read")
			if invoice.docstatus != 1 or invoice.company != doc.company or invoice.crane_maintenance != job.name or invoice.is_return:
				frappe.throw(_("Select a submitted repair service invoice from this maintenance job."))
			if job.get("repair_source") != "Supplier Bill" and (invoice.update_stock or any(frappe.get_cached_value("Item", r.item_code, "is_stock_item") for r in invoice.items)):
				frappe.throw(_("Purchased parts are capitalized through stock consumption. The Asset Repair invoice field is only for services."))
			if len({r.expense_account for r in invoice.items if not frappe.get_cached_value("Item", r.item_code, "is_stock_item")}) != 1 or invoice.currency != frappe.get_cached_value("Company", doc.company, "default_currency"):
				frappe.throw(_("Capitalization requires a company-currency service invoice using one Expense account."))
			from erpnext.assets.doctype.asset_repair.asset_repair import get_repair_cost_for_purchase_invoice
			doc.repair_cost = get_repair_cost_for_purchase_invoice(invoice.name)
		elif flt(doc.repair_cost):
			frappe.throw(_("A posted service Purchase Invoice is required for non-stock capitalized costs."))
		if not doc.stock_consumption and not flt(doc.repair_cost):
			frappe.throw(_("Enter consumed stock or a posted service invoice for the improvement."))
		if doc.purchase_invoice and frappe.db.exists("Asset Repair", {"purchase_invoice": doc.purchase_invoice,
			"docstatus": ["!=", 2], "name": ["!=", doc.name]}):
			frappe.throw(_("This service invoice is already assigned to another Asset Repair."))
		doc.calculate_total_repair_cost()
		if asset.status == "Fully Depreciated":
			frappe.throw(_("This ERPNext version does not support this improvement on a fully depreciated Asset. Review a native Asset Capitalization/replacement with accounting."))
	for row in doc.get("items") or []:
		if row.meta.has_field("crane"):
			row.crane = job.crane


def guard_repair_posting(doc, method=None):
	if not doc.get("crane_maintenance"):
		return
	job = frappe.get_doc("Crane Maintenance", doc.crane_maintenance, for_update=True)
	lock_cranes([job.crane])
	from heavy_equipment_rental.timesheet_settlement import guard_source_snapshots
	guard_source_snapshots(doc, [job.crane])
	if method == "before_cancel" and job.docstatus == 1:
		frappe.throw(_("Cancel Crane Maintenance {0} to reverse its related documents together.").format(job.name))
	if job.cost_treatment == "Operating Expense":
		from heavy_equipment_rental.rental_expenses import guard_expense
		context = frappe._dict(crane=job.crane, company=job.company, crane_assignment=job.crane_assignment,
			crane_timesheet=job.crane_timesheet, posting_date=doc.get("posting_date") or today())
		context.service_from_date = job.actual_start_date or context.posting_date
		context.service_to_date = job.actual_end_date or context.service_from_date
		if job.crane_timesheet:
			context.service_from_date, context.service_to_date = frappe.db.get_value(
				"Crane Timesheet", job.crane_timesheet, ["period_start", "period_end"])
		guard_expense(context)
	if doc.doctype == "Purchase Invoice" and method == "before_cancel" and job.get("repair_source") in ("External Parts", "Supplier Bill"):
		if frappe.db.exists("Stock Entry", {"crane_maintenance": job.name, "docstatus": 1}):
			frappe.throw(_("Cancel the repair Material Issue before cancelling its parts Purchase Invoice."))
	if doc.doctype == "Purchase Invoice" and method == "before_cancel" and frappe.db.exists(
		"Asset Repair", {"purchase_invoice": doc.name, "docstatus": 1}):
		frappe.throw(_("Cancel the Asset Repair before its capitalized service invoice."))
	if doc.doctype == "Stock Entry" and doc.get("asset_repair") and method == "before_cancel":
		if frappe.db.get_value("Asset Repair", doc.asset_repair, "docstatus") == 1:
			frappe.throw(_("Cancel the Asset Repair to reverse its consumed stock and capitalized value together."))


def repair_expense_sources(crane, company):
	"""Read actual posted costs with explicit work links for settlement allocation."""
	for _, source in fleet_repair_expenses([crane], company):
		yield source


def fleet_repair_expenses(cranes, company, dates=None):
	if not cranes:
		return
	filters = {"crane": ["in", list(cranes)], "company": company, "docstatus": 1, "crane_maintenance": ["is", "set"]}
	if dates:
		filters["posting_date"] = ["between", dates]
	for doctype in ("Stock Entry", "Purchase Invoice"):
		for name in frappe.get_all(doctype, filters=filters, pluck="name"):
			doc = frappe.get_doc(doctype, name)
			job = frappe.get_doc("Crane Maintenance", doc.crane_maintenance)
			if job.cost_treatment != "Operating Expense":
				continue
			doc.check_permission("read")
			job.check_permission("read")
			amount = sum(flt(r.debit) - flt(r.credit) for r in frappe.get_all("GL Entry", filters={
				"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
				fields=["account", "debit", "credit"])
				if frappe.get_cached_value("Account", r.account, "root_type") == "Expense")
			start, end = job.actual_start_date or doc.posting_date, job.actual_end_date or job.actual_start_date or doc.posting_date
			if job.crane_timesheet:
				start, end = frappe.db.get_value("Crane Timesheet", job.crane_timesheet, ["period_start", "period_end"])
			if amount:
				yield doc.crane, dict(doctype=doctype, name=name, posting_date=str(doc.posting_date),
					basis="Selected Timesheet" if job.crane_timesheet else "Selected Rental Contract / worked hours" if job.crane_assignment else "Unallocated crane repair", expenses=amount,
					rental_assignment=job.crane_assignment, rental_timesheet=job.crane_timesheet,
					service_from_date=str(start), service_to_date=str(end))


def allocate_repair_period(source, company, start, end):
	from heavy_equipment_rental.profit_sharing import allocate_amount
	if not source.get("rental_assignment") and not source.get("rental_timesheet"):
		return None
	first, last = getdate(source["service_from_date"]), getdate(source["service_to_date"])
	left, right = max(first, getdate(start)), min(last, getdate(end))
	if left > right:
		return None
	precision = frappe.get_precision("Crane Profit Settlement", "revenue",
		currency=frappe.get_cached_value("Company", company, "default_currency"))
	days = (last - first).days + 1
	daily = allocate_amount(source["expenses"], [1] * days, precision)
	offset = (left - first).days
	return dict(source, source_amount=source["expenses"],
		expenses=flt(sum(daily[offset:offset + (right - left).days + 1]), precision),
		allocation_from_date=str(left), allocation_to_date=str(right))


def validate_repair_closure(settlement):
	"""Do not close distributions while relevant repair costs are still pending."""
	for name in frappe.get_all("Crane Maintenance", filters={"crane": settlement.crane,
		"status": ["in", ["Planned", "In Progress"]]}, pluck="name"):
		job = frappe.get_doc("Crane Maintenance", name)
		if job.cost_treatment != "Operating Expense":
			continue
		from heavy_equipment_rental.rental_expenses import settlement_matches
		first = job.actual_start_date or today()
		last = job.actual_end_date or first
		if job.crane_timesheet:
			first, last = frappe.db.get_value("Crane Timesheet", job.crane_timesheet, ["period_start", "period_end"])
		if settlement_matches(job, settlement, getdate(first), getdate(last)):
			frappe.throw(_("Complete or cancel repair {0} before closing its profit settlement.").format(name))


def attribute_depreciation(doc, method=None):
	if doc.voucher_type != "Depreciation Entry":
		return
	for row in doc.accounts:
		if row.reference_type == "Asset" and row.reference_name:
			crane = frappe.db.get_value("Crane", {"asset": row.reference_name}, "name")
			if crane:
				if row.get("crane") and row.crane != crane:
					frappe.throw(_("Depreciation Crane must match the referenced Asset."))
				row.crane = crane
