"""Partner entitlements and movements, reconciled against the native payment ledger."""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today

from heavy_equipment_rental.partner_accounts import share_party
from heavy_equipment_rental.profit_sharing import allocate_amount


def partner_balances(doc, report_date=None):
    report_date = report_date or today()
    if doc.journal_entry:
        frappe.get_doc("Journal Entry", doc.journal_entry).check_permission("read")
    result = []
    for share in doc.shares:
        if share.is_company:
            continue
        party_type, party = share_party(share)
        frappe.get_doc(party_type, party).check_permission("read")
        shareholder = party if party_type == "Shareholder" else frappe.db.get_value("Shareholder",
            {"crane_partner_supplier": party, "company": doc.company}, "name")
        if shareholder and party_type != "Shareholder":
            frappe.get_doc("Shareholder", shareholder).check_permission("read")
        entries = []
        outstanding = 0
        if doc.docstatus == 1 and doc.journal_entry:
            entries = frappe.get_all("Payment Ledger Entry", filters={"company": doc.company,
                "against_voucher_type": "Journal Entry", "against_voucher_no": doc.journal_entry,
                "party_type": party_type, "party": party, "delinked": 0, "posting_date": ["<=", report_date]},
                fields=["voucher_type", "voucher_no", "posting_date", "amount_in_account_currency"],
                order_by="posting_date, creation")
            for kind, name in {(e.voucher_type, e.voucher_no) for e in entries}:
                frappe.get_doc(kind, name).check_permission("read")
            outstanding = flt(sum(e.amount_in_account_currency for e in entries), doc.precision("revenue"))
        paid = flt(share.amount - outstanding, doc.precision("revenue")) if doc.docstatus == 1 else 0
        invoice_pending = doc.timesheet and (not doc.sales_invoice or frappe.db.get_value("Sales Invoice", doc.sales_invoice, "docstatus") != 1)
        status = ("Awaiting Invoice" if invoice_pending else "Draft") if doc.docstatus == 0 else (
            "No Entitlement" if not share.amount else "Paid" if outstanding <= 0 else "Partly Paid" if paid > 0 else "Unpaid")
        name_field = "title" if party_type == "Shareholder" else "supplier_name"
        result.append(dict(shareholder=shareholder, party_type=party_type, party=party,
            partner_name=frappe.get_cached_value(party_type, party, name_field),
            entitlement=share.amount if doc.docstatus == 1 else 0, pending_entitlement=share.amount if doc.docstatus == 0 else 0,
            operating_amount=share.operating_amount, residual_amount=share.residual_amount,
            paid_amount=paid, outstanding_amount=outstanding, status=status, entries=entries))
    return result


@frappe.whitelist()
def settlement_payment_details(settlement):
    doc = frappe.get_doc("Crane Profit Settlement", settlement)
    doc.check_permission("read")
    frappe.has_permission("Payment Entry", "read", throw=True)
    balances = partner_balances(doc)
    payments = []
    if doc.journal_entry:
        names = frappe.get_all("Payment Entry", filters=[
            ["Payment Entry", "docstatus", "!=", 2],
            ["Payment Entry", "payment_type", "=", "Pay"],
            ["Payment Entry Reference", "reference_doctype", "=", "Journal Entry"],
            ["Payment Entry Reference", "reference_name", "=", doc.journal_entry],
        ], pluck="name", distinct=True)
        for name in names:
            payment = frappe.get_doc("Payment Entry", name)
            payment.check_permission("read")
            payments.append(dict(name=name, posting_date=payment.posting_date, party=payment.party,
                party_name=payment.party_name, docstatus=payment.docstatus,
                amount=sum(r.allocated_amount for r in payment.references
                    if r.reference_doctype == "Journal Entry" and r.reference_name == doc.journal_entry)))
    for row in balances:
        row.pop("entries")
    return dict(balances=balances, payments=payments)


def validate_payment(doc, method=None):
    names = [r.reference_name for r in doc.references if r.reference_doctype == "Journal Entry" and r.allocated_amount]
    if not names:
        if doc.crane_profit_settlement:
            frappe.throw(_("The payment must reference its submitted settlement Journal Entry."))
        return
    settlements = frappe.get_all("Crane Profit Settlement", filters={"journal_entry": ["in", names], "docstatus": 1},
        fields=["name", "timesheet", "crane", "journal_entry"])
    if doc.crane_profit_settlement:
        match = next((s for s in settlements if s.name == doc.crane_profit_settlement), None)
        if not match:
            frappe.throw(_("The payment must reference its submitted settlement Journal Entry."))
        if doc.payment_type != "Pay":
            frappe.throw(_("Partner settlement payments must use payment type Pay."))
        source = frappe.get_doc("Crane Profit Settlement", match.name)
        source.check_permission("read")
        if not any(not r.is_company and share_party(r) == (doc.party_type, doc.party) for r in source.shares):
            frappe.throw(_("Select a partner from this settlement."))
        doc.crane_timesheet, doc.crane = match.timesheet, match.crane
    elif len(settlements) == 1 and doc.payment_type == "Pay":
        doc.crane_profit_settlement = settlements[0].name
        doc.crane_timesheet, doc.crane = settlements[0].timesheet, settlements[0].crane


def lock_payment_settlements(doc, method=None):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

    for reference in sorted(doc.references, key=lambda r: r.reference_name or ""):
        if reference.reference_doctype != "Journal Entry" or not reference.allocated_amount:
            continue
        if not frappe.db.exists("Crane Profit Settlement", {"journal_entry": reference.reference_name, "docstatus": 1}):
            continue
        frappe.get_doc("Journal Entry", reference.reference_name, for_update=True)
        details = get_reference_details("Journal Entry", reference.reference_name,
            doc.party_account_currency, doc.party_type, doc.party)
        if flt(reference.allocated_amount, doc.precision("paid_amount")) > flt(details.outstanding_amount, doc.precision("paid_amount")):
            frappe.throw(_("Payment exceeds the remaining partner entitlement. Reload the settlement."))


def execute_report(filters=None, summary=False):
    filters = frappe._dict(filters or {})
    if not filters.company or not filters.report_date:
        frappe.throw(_("Company and Report Date are required."))
    if filters.from_date and getdate(filters.from_date) > getdate(filters.report_date):
        frappe.throw(_("From Date must be before Report Date."))
    frappe.get_doc("Company", filters.company).check_permission("read")
    for doctype in ("Crane Profit Settlement", "Crane Timesheet", "Sales Invoice", "Journal Entry", "Payment Entry", "Shareholder"):
        frappe.has_permission(doctype, "read", throw=True)
    query = {"company": filters.company, "docstatus": ["in", [0, 1]], "posting_date": ["<=", filters.report_date]}
    if filters.from_date:
        query["posting_date"] = ["between", [filters.from_date, filters.report_date]]
    if filters.crane:
        query["crane"] = filters.crane
    if filters.timesheet:
        query["timesheet"] = filters.timesheet
    rows = []
    for name in frappe.get_list("Crane Profit Settlement", filters=query, pluck="name", order_by="posting_date, name", limit_page_length=0):
        doc = frappe.get_doc("Crane Profit Settlement", name)
        doc.check_permission("read")
        frappe.get_doc("Crane", doc.crane).check_permission("read")
        for source in json.loads(doc.source_snapshot or "[]"):
            frappe.get_doc(source["doctype"], source["name"]).check_permission("read")
        if doc.timesheet:
            timesheet = frappe.get_doc("Crane Timesheet", doc.timesheet)
            timesheet.check_permission("read")
            if doc.settlement_basis == "Timesheet" and timesheet.docstatus != 1:
                continue
        if doc.sales_invoice:
            frappe.get_doc("Sales Invoice", doc.sales_invoice).check_permission("read")
        balances = partner_balances(doc, filters.report_date)
        total = sum(max(b["entitlement"] + b["pending_entitlement"], 0) for b in balances)
        invoice_values = allocate_amount(doc.revenue, [max(b["entitlement"] + b["pending_entitlement"], 0)
            for b in balances], doc.precision("revenue")) if total else [0 for b in balances]
        for balance, invoice_value in zip(balances, invoice_values):
            if filters.shareholder and balance["shareholder"] != filters.shareholder:
                continue
            if filters.status and balance["status"] != filters.status:
                continue
            # A shared invoice is shown once in totals, proportioned over its external entitlements.
            age = max(date_diff(filters.report_date, doc.posting_date), 0)
            row = dict(settlement=doc.name, timesheet=doc.timesheet, crane=doc.crane,
                sales_invoice=doc.sales_invoice, posting_date=doc.posting_date,
                currency=doc.currency, **{k: v for k, v in balance.items() if k != "entries"},
                invoice_value=invoice_value, invoice_grand_total=str(doc.revenue),
                age=age, movement_type=_("Entitlement") if doc.docstatus == 1 else _(balance["status"]),
                voucher_type="Journal Entry" if doc.journal_entry else "Crane Profit Settlement",
                voucher_no=doc.journal_entry or doc.name)
            for label, low, high in (("range1", 0, 30), ("range2", 31, 60), ("range3", 61, 90), ("range4", 91, 10**9)):
                row[label] = balance["outstanding_amount"] if low <= age <= high else 0
            if summary:
                rows.append(row)
                continue
            # Payment movements carry their amounts; the entitlement row carries the final balance.
            row["paid_amount"] = 0
            rows.append(row)
            grouped = defaultdict(float)
            for entry in balance["entries"]:
                if entry.voucher_no != doc.journal_entry:
                    grouped[(entry.posting_date, entry.voucher_type, entry.voucher_no)] -= entry.amount_in_account_currency
            for (day, kind, voucher), paid in grouped.items():
                frappe.get_doc(kind, voucher).check_permission("read")
                rows.append(dict(posting_date=day, settlement=doc.name, timesheet=doc.timesheet, crane=doc.crane,
                    shareholder=balance["shareholder"], partner_name=balance["partner_name"],
                    voucher_type=kind, voucher_no=voucher, movement_type=_("Payment / Adjustment"),
                    paid_amount=paid, currency=doc.currency, status=balance["status"]))
    if summary:
        grouped = {}
        for row in rows:
            key = row["shareholder"] or row["party"]
            target = grouped.setdefault(key, dict(shareholder=row["shareholder"], partner_name=row["partner_name"], currency=row["currency"]))
            target.setdefault("_statuses", set()).add(row["status"])
            for field in ("invoice_value", "entitlement", "pending_entitlement", "operating_amount", "residual_amount", "paid_amount", "outstanding_amount", "range1", "range2", "range3", "range4"):
                target[field] = target.get(field, 0) + flt(row.get(field))
        rows = list(grouped.values())
        for row in rows:
            statuses = row.pop("_statuses")
            if row["outstanding_amount"]:
                row["status"] = "Partly Paid" if row["paid_amount"] else "Unpaid"
            elif "Awaiting Invoice" in statuses or "Draft" in statuses:
                row["status"] = "Draft" if "Draft" in statuses else "Awaiting Invoice"
            else:
                row["status"] = "Paid" if row["entitlement"] else "No Entitlement"
    return columns(summary), rows, _("Invoice Value is allocated across external partners so shared invoices are not counted twice. Payments and balances use the native payment ledger as of Report Date. Draft amounts are not posted entitlements.")


def columns(summary):
    def col(fieldname, label, fieldtype="Currency", options="currency", width=135):
        return dict(fieldname=fieldname, label=_(label), fieldtype=fieldtype, options=options, width=width)
    result = [col("shareholder", "Shareholder", "Link", "Shareholder", 155), col("partner_name", "Partner Name", "Data", None, 170)]
    if not summary:
        result += [col("posting_date", "Posting Date", "Date", None, 105),
            col("settlement", "Settlement", "Link", "Crane Profit Settlement", 135),
            col("timesheet", "Timesheet", "Link", "Crane Timesheet"), col("crane", "Crane", "Link", "Crane"),
            col("sales_invoice", "Sales Invoice", "Link", "Sales Invoice", 175),
            col("movement_type", "Movement", "Data", None), col("voucher_type", "Voucher Type", "Data", None),
            col("voucher_no", "Voucher", "Dynamic Link", "voucher_type", 180),
            col("invoice_grand_total", "Settlement Invoice Total", "Data", None, 150)]
    result += [col("invoice_value", "Allocated Invoice Value"), col("entitlement", "Posted Entitlement"),
        col("pending_entitlement", "Pending Entitlement"), col("operating_amount", "Operating Share"),
        col("residual_amount", "Remaining Balance Share"), col("paid_amount", "Paid / Adjusted"),
        col("outstanding_amount", "Outstanding"), col("status", "Entitlement Status", "Data", None, 140)]
    if summary:
        result += [col("range1", "0-30 Days"), col("range2", "31-60 Days"), col("range3", "61-90 Days"), col("range4", "91+ Days")]
    result.append(dict(fieldname="currency", label=_("Currency"), fieldtype="Link", options="Currency", hidden=1))
    return result
