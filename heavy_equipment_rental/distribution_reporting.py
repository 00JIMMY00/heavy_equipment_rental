"""Saved settlement economics and native-ledger balances, without reposting anything."""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, strip_html

from heavy_equipment_rental.partner_accounts import share_party
from heavy_equipment_rental.partner_reporting import partner_balances
from heavy_equipment_rental.profit_sharing import allocate_amount

VIEWS = ("Settlement Summary", "Participant Summary", "Distribution Details", "Source Details", "Entitlement Movements")


class ReportContext:
    def __init__(self):
        self.docs = {}

    def doc(self, doctype, name):
        key = (doctype, name)
        if key not in self.docs:
            doc = frappe.get_doc(doctype, name)
            doc.check_permission("read")
            self.docs[key] = doc
        return self.docs[key]


def execute(filters=None, *, dashboard=False):
    f = frappe._dict(filters or {})
    f.view = f.view or VIEWS[0]
    f.date_basis = f.date_basis or "Work Period"
    f.settlement_status = f.settlement_status or "Submitted"
    f.participant = f.participant or "All"
    if not f.company or not f.report_date:
        frappe.throw(_("Company and Balance As Of are required."))
    if f.view not in VIEWS or f.date_basis not in ("Work Period", "Settlement Posting Date"):
        frappe.throw(_("Invalid report view or date basis."))
    if f.settlement_status not in ("Submitted", "Draft", "All") or f.participant not in ("All", "Our Company", "External Partners"):
        frappe.throw(_("Invalid settlement status or participant."))
    if f.payment_status and f.payment_status not in ("Unpaid", "Partly Paid", "Paid", "No Entitlement", "Draft", "Awaiting Invoice"):
        frappe.throw(_("Invalid entitlement status."))
    if f.from_date and f.to_date and getdate(f.from_date) > getdate(f.to_date):
        frappe.throw(_("From Date must be before To Date."))
    if f.from_date and getdate(f.from_date) > getdate(f.report_date):
        frappe.throw(_("From Date must be before Balance As Of."))
    if f.to_date and getdate(f.to_date) > getdate(f.report_date):
        frappe.throw(_("To Date must be before Balance As Of."))
    ctx = ReportContext()
    company = ctx.doc("Company", f.company)
    precision = frappe.get_precision("Crane Profit Settlement", "revenue", currency=company.default_currency)
    for doctype in ("Crane Profit Settlement", "Crane", "Crane Timesheet", "Crane Assignment",
                    "Sales Invoice", "Journal Entry", "Payment Entry", "Shareholder"):
        frappe.has_permission(doctype, "read", throw=True)
    if f.shareholder and ctx.doc("Shareholder", f.shareholder).company != f.company:
        frappe.throw(_("Select a Shareholder in the report Company."))
    query = {"company": f.company, "docstatus": {"Submitted": 1, "Draft": 0, "All": ["in", [0, 1]]}[f.settlement_status],
             "posting_date": ["<=", f.report_date]}
    for field in ("crane", "timesheet"):
        if f.get(field):
            query[field] = f[field]
    if f.settlement:
        query["name"] = f.settlement
    selected = []
    for name in frappe.get_list("Crane Profit Settlement", filters=query, pluck="name",
                                order_by="from_date, crane, name", limit_page_length=0):
        doc = ctx.doc("Crane Profit Settlement", name)
        low, high = (doc.from_date, doc.to_date) if f.date_basis == "Work Period" else (doc.posting_date, doc.posting_date)
        if (f.from_date and getdate(high) < getdate(f.from_date)) or (f.to_date and getdate(low) > getdate(f.to_date)):
            continue
        ctx.doc("Crane", doc.crane)
        sources = json.loads(doc.source_snapshot or "[]")
        assignments, customers, invoices = set(), set(), set()
        if doc.timesheet:
            sheet = ctx.doc("Crane Timesheet", doc.timesheet)
            if doc.settlement_basis == "Timesheet" and sheet.docstatus != 1:
                continue
            if sheet.assignment:
                assignments.add(sheet.assignment)
            if sheet.customer:
                customers.add(sheet.customer)
        if doc.sales_invoice:
            invoices.add(doc.sales_invoice)
        for source in sources:
            ctx.doc(source["doctype"], source["name"])
            if source.get("journal"):
                ctx.doc("Journal Entry", source["journal"])
            if source.get("rental_assignment"):
                assignments.add(source["rental_assignment"])
            if source["doctype"] == "Sales Invoice":
                invoices.add(source["name"])
        for assignment in assignments:
            customer = ctx.doc("Crane Assignment", assignment).customer
            if customer:
                customers.add(customer)
        for invoice in invoices:
            customers.add(ctx.doc("Sales Invoice", invoice).customer)
        if f.sales_invoice and f.sales_invoice not in invoices:
            continue
        if (f.assignment and f.assignment not in assignments) or (f.customer and f.customer not in customers):
            continue
        if doc.docstatus == 1 and doc.journal_entry:
            journal = ctx.doc("Journal Entry", doc.journal_entry)
            if getdate(journal.posting_date) > getdate(f.report_date):
                continue
        balances = partner_balances(doc, f.report_date)
        matching = [b for b in balances if (not f.shareholder or b["shareholder"] == f.shareholder)
                    and (not f.payment_status or b["status"] == f.payment_status)]
        if (f.shareholder or f.payment_status) and not matching:
            continue
        common = dict(settlement=doc.name, crane=doc.crane, crane_name=ctx.doc("Crane", doc.crane).crane_name,
                      timesheet=doc.timesheet, sales_invoice=doc.sales_invoice,
                      assignment=next(iter(assignments)) if len(assignments) == 1 else None,
                      customer=next(iter(customers)) if len(customers) == 1 else None,
                      posting_date=doc.posting_date, from_date=doc.from_date, to_date=doc.to_date,
                      currency=doc.currency, settlement_status=_("Submitted") if doc.docstatus == 1 else _("Draft"),
                      journal_entry=doc.journal_entry)
        selected.append(dict(doc=doc, sources=sources, balances=balances, matching=matching, common=common))
    rows = []
    for record in selected:
        if f.view == "Settlement Summary":
            rows.append(summary_row(record))
        elif f.view in ("Distribution Details", "Participant Summary"):
            rows.extend(distribution_rows(record, f))
        elif f.view == "Source Details":
            rows.extend(source_rows(record, ctx))
        else:
            rows.extend(movement_rows(record, f))
    if f.view == "Participant Summary":
        rows = aggregate_participants(rows)
    cols = columns(f.view, bool(f.shareholder or f.payment_status))
    # Posted and draft figures have separate totals, even in the All view.
    total_groups = defaultdict(list)
    for row in rows:
        total_groups[row["settlement_status"]].append(row)
    for status, group in total_groups.items():
        total = dict(settlement_status=_("Total") + " — " + status,
                     currency=company.default_currency, is_total_row=1)
        for col in cols:
            if col["fieldtype"] == "Currency" and col["fieldname"] != "running_balance":
                total[col["fieldname"]] = flt(sum(flt(row.get(col["fieldname"])) for row in group), precision)
        rows.append(total)
    message = _("Whole saved settlements are selected by overlapping work dates or settlement posting date; amounts are not prorated by report filters. Summary cards include each selected settlement once. Company retention is not a cash balance. Paid / Adjusted and outstanding use the native payment ledger through Balance As Of. Drafts are estimates, not posted entitlements.")
    if any(r["doc"].docstatus == 0 for r in selected):
        message += " " + _("Draft figures are the last saved calculation. Recalculate the settlement after changing sources; the report does not refresh or post it.")
    if f.shareholder or f.payment_status:
        message += " " + _("Partner and payment-status filters select matching settlements. Summary cards retain the full settlement context; Distribution Details and Entitlement Movements show only matching external partners. Source Details includes all selected settlement sources.")
    if f.view in ("Distribution Details", "Participant Summary"):
        message += " " + _("Expense Burden compares rounded residual shares before and after saved costs, after prior losses. Deficit drafts may contain costs beyond the distributable pool. This is explanatory, not another expense posting. Ownership % and Remaining Balance % are independent.")
    if any(getdate(s.get("posting_date") or r["doc"].posting_date) > getdate(f.report_date)
           for r in selected for s in r["sources"]):
        message += " " + _("Some saved source postings are later than Balance As Of; this report preserves the settlement snapshot rather than reconstructing an earlier cost estimate.")
    if dashboard:
        statuses = defaultdict(int)
        for record in selected:
            for balance in record["matching"]:
                statuses[balance["status"]] += 1
        return dict(columns=cols, rows=rows, message=message,
            cards=cards(selected, company.default_currency, f), currency=company.default_currency, precision=precision,
            settlement_count=len(selected), statuses=dict(statuses))
    return cols, rows, message, None, cards(selected, company.default_currency, f), True


def paid_parts(balance, precision):
    cash = sum(-flt(e.amount_in_account_currency) for e in balance["entries"] if e.voucher_type == "Payment Entry")
    return flt(cash, precision), flt(balance["paid_amount"] - cash, precision)


def summary_row(record):
    d, balances = record["doc"], record["balances"]
    ours = [s for s in d.shares if s.is_company]
    row = dict(record["common"], revenue=d.revenue, operating_percentage=d.operating_percentage,
        operating_fee=d.operating_fee, balance_after_operating=d.balance_after_operating,
        expenses=d.operating_expenses, loss_brought_forward=d.loss_brought_forward,
        residual_pool=d.distributable_profit, company_operating=sum(s.operating_amount for s in ours),
        company_residual=sum(s.residual_amount for s in ours), company_total=d.company_retained,
        external_total=d.external_distribution, posted_entitlement=sum(b["entitlement"] for b in balances),
        pending_entitlement=sum(b["pending_entitlement"] for b in balances),
        cash_paid=sum(paid_parts(b, d.precision("revenue"))[0] for b in balances), adjustments=sum(paid_parts(b, d.precision("revenue"))[1] for b in balances),
        outstanding=sum(b["outstanding_amount"] for b in balances))
    row.update(selected_entitlement=sum(b["entitlement"] for b in record["matching"]),
        selected_paid=sum(b["paid_amount"] for b in record["matching"]),
        selected_outstanding=sum(b["outstanding_amount"] for b in record["matching"]))
    return row


def distribution_rows(record, filters):
    d = record["doc"]
    precision = d.precision("revenue")
    weights = [flt(s.profit_percentage) for s in d.shares]
    before_pool = max(flt(d.balance_after_operating - d.loss_brought_forward, precision), 0)
    before_costs = allocate_amount(before_pool, weights, precision) if sum(weights) else [0] * len(weights)
    # Compare the rounded allocations, rather than rounding a second allocation
    # of costs. Those can differ by a cent and misstate an individual share.
    burdens = [flt(before - share.residual_amount, precision) for before, share in zip(before_costs, d.shares)]
    balances = {(b["party_type"], b["party"]): b for b in record["matching"]}
    rows = []
    for share, burden in zip(d.shares, burdens):
        if share.is_company:
            if filters.participant == "External Partners" or filters.shareholder or filters.payment_status:
                continue
            values = dict(participant=_("Our Company"), partner_name=d.company, status=_("Retained by Company"))
        else:
            if filters.participant == "Our Company":
                continue
            balance = balances.get(share_party(share))
            if not balance:
                continue
            cash, adjustments = paid_parts(balance, precision)
            values = {k: v for k, v in balance.items() if k != "entries"}
            values.update(participant=_("External Partner"), cash_paid=cash, adjustments=adjustments,
                posted_entitlement=balance["entitlement"])
        rows.append(dict(record["common"], **values, ownership_percentage=share.ownership_percentage,
            profit_percentage=share.profit_percentage, expense_burden=burden,
            residual_before_costs=flt(share.residual_amount + burden, precision),
            operating_share=share.operating_amount, residual_share=share.residual_amount, total_share=share.amount))
    return rows


def aggregate_participants(rows):
    grouped = {}
    for row in rows:
        key = (row["settlement_status"], row.get("shareholder") or row["partner_name"])
        target = grouped.setdefault(key, {k: row.get(k) for k in (
            "participant", "shareholder", "partner_name", "currency", "settlement_status")})
        target.setdefault("_settlements", set()).add(row["settlement"])
        for field in ("expense_burden", "residual_before_costs", "operating_share", "residual_share", "total_share",
                      "posted_entitlement", "pending_entitlement", "cash_paid", "adjustments", "outstanding_amount"):
            if field in row:
                target[field] = target.get(field, 0) + flt(row[field])
    for row in grouped.values():
        row["settlement_count"] = len(row.pop("_settlements"))
        if row["participant"] == _("Our Company"):
            row["status"] = _("Retained by Company")
        elif row["settlement_status"] == _("Draft"):
            row["status"] = "Draft"
        elif not row.get("posted_entitlement"):
            row["status"] = "No Entitlement"
        elif row.get("outstanding_amount", 0) <= 0:
            row["status"] = "Paid"
        else:
            row["status"] = "Partly Paid" if row.get("cash_paid", 0) + row.get("adjustments", 0) > 0 else "Unpaid"
    return list(grouped.values())


def source_rows(record, ctx):
    rows = []
    for source in record["sources"]:
        doc = ctx.doc(source["doctype"], source["name"])
        description = doc.get("description") or doc.get("remarks") or doc.get("user_remark") or doc.get("title") or ""
        details = [(None, source.get("expenses", 0), description)]
        if doc.doctype == "Expense Entry" and source.get("expenses"):
            weights = [flt(r.amount) for r in doc.expenses]
            amounts = allocate_amount(source["expenses"], weights, record["doc"].precision("revenue")) if sum(weights) else []
            details = [(r.expense_entry_type, amount, description) for r, amount in zip(doc.expenses, amounts)] or details
        for expense_type, expense, text in details:
            label = ctx.doc("Expense Entry Type", expense_type).title if expense_type else None
            rows.append(dict(record["common"], source_doctype=doc.doctype, source_name=doc.name,
                source_posting_date=source.get("posting_date"), detail=source.get("detail"),
                description=strip_html(text), expense_type=label,
                income_account=source.get("income_account"), revenue=flt(source.get("revenue")), expenses=flt(expense),
                source_original_amount=str(source.get("source_amount", "")),
                allocation_basis=source.get("basis"), service_from_date=source.get("service_from_date"),
                service_to_date=source.get("service_to_date")))
    return rows


def movement_rows(record, filters):
    rows = []
    if filters.participant == "Our Company":
        return rows
    for balance in record["matching"]:
        grouped = defaultdict(float)
        for entry in balance["entries"]:
            grouped[(str(entry.posting_date), entry.voucher_type, entry.voucher_no)] += flt(entry.amount_in_account_currency)
        running = 0
        # partner_balances orders native entries by posting date and creation.
        # Preserve that order instead of reordering same-day adjustments by name.
        for (day, kind, name), amount in grouped.items():
            running = flt(running + amount, record["doc"].precision("revenue"))
            rows.append(dict(record["common"], shareholder=balance["shareholder"], partner_name=balance["partner_name"],
                movement_date=day, voucher_type=kind, voucher_no=name,
                movement=_("Entitlement") if name == record["doc"].journal_entry and kind == "Journal Entry" else _("Payment / Adjustment"),
                increase=max(amount, 0), decrease=max(-amount, 0), running_balance=running, status=balance["status"]))
    return rows


def cards(records, currency, filters):
    precision = frappe.get_precision("Crane Profit Settlement", "revenue", currency=currency)
    totals = defaultdict(float)
    for record in records:
        if record["doc"].docstatus != 1:
            totals["drafts"] += record["doc"].external_distribution
            continue
        row = summary_row(record)
        for key in ("revenue", "expenses", "company_operating", "company_residual", "company_total", "posted_entitlement",
                    "cash_paid", "adjustments", "outstanding", "selected_entitlement", "selected_paid", "selected_outstanding"):
            totals[key] += flt(row[key])
    result = [dict(label=_(label), value=flt(totals[key], precision), datatype="Currency", currency=currency, indicator=color)
        for key, label, color in (
            ("revenue", "Posted Settlement Revenue", "Blue"), ("expenses", "Settlement Costs", "Orange"),
            ("company_operating", "Company Operating Share", "Green"), ("company_residual", "Company Residual Share", "Green"),
            ("company_total", "Company Total Retention", "Green"), ("posted_entitlement", "Partners Posted Entitlement", "Blue"),
            ("cash_paid", "Partner Payments", "Green"), ("adjustments", "Other Partner Adjustments", "Gray"),
            ("outstanding", "Partners Outstanding", "Red"), ("drafts", "Draft Partner Estimates", "Gray"))]
    if filters.shareholder or filters.payment_status:
        result += [dict(label=_(label), value=flt(totals[key], precision), datatype="Currency", currency=currency, indicator="Blue")
            for key, label in (("selected_entitlement", "Filtered Partners Entitlement"), ("selected_paid", "Filtered Partners Paid / Adjusted"),
                               ("selected_outstanding", "Filtered Partners Outstanding"))]
    return result


def columns(view, filtered=False):
    def c(key, label, kind="Currency", options="currency", width=145):
        return dict(fieldname=key, label=_(label), fieldtype=kind, options=options, width=width)
    common = [c("settlement", "Settlement", "Link", "Crane Profit Settlement"), c("crane", "Crane", "Link", "Crane", 125),
              c("crane_name", "Crane Name", "Data", None, 150), c("settlement_status", "Settlement Status", "Data", None)]
    context = [c("from_date", "Work From", "Date", None, 110), c("to_date", "Work To", "Date", None, 110),
        c("posting_date", "Settlement Posting Date", "Date", None, 130),
        c("assignment", "Assignment", "Link", "Crane Assignment"), c("timesheet", "Timesheet", "Link", "Crane Timesheet"),
        c("sales_invoice", "Sales Invoice", "Link", "Sales Invoice", 175), c("customer", "Customer", "Link", "Customer"),
        c("journal_entry", "Entitlement Journal", "Link", "Journal Entry", 175)]
    if view == "Settlement Summary":
        detail = [c("revenue", "Settlement Revenue"), c("operating_percentage", "Operating %", "Percent", None, 110),
            c("operating_fee", "Total Operating Share"), c("balance_after_operating", "After Operating Share"),
            c("expenses", "Settlement Costs"), c("loss_brought_forward", "Loss Brought Forward"), c("residual_pool", "Residual Pool"),
            c("company_operating", "Company Operating Share"), c("company_residual", "Company Residual Share"),
            c("company_total", "Company Total Retention"), c("external_total", "Partners Calculated Share"),
            c("posted_entitlement", "Partners Posted Entitlement"), c("pending_entitlement", "Draft Partner Estimates"),
            c("cash_paid", "Partner Payments"), c("adjustments", "Other Partner Adjustments"), c("outstanding", "Partners Outstanding")]
        if filtered:
            detail += [c("selected_entitlement", "Filtered Partners Entitlement"), c("selected_paid", "Filtered Partners Paid / Adjusted"),
                       c("selected_outstanding", "Filtered Partners Outstanding")]
    elif view in ("Distribution Details", "Participant Summary"):
        detail = [c("participant", "Participant", "Data", None), c("shareholder", "Shareholder", "Link", "Shareholder"),
            c("partner_name", "Participant Name", "Data", None, 200),
            c("ownership_percentage", "Ownership %", "Percent", None, 110), c("profit_percentage", "Remaining Balance %", "Percent", None, 135),
            c("operating_share", "Operating Share"), c("residual_before_costs", "Residual Before These Costs"),
            c("expense_burden", "Expense Burden"), c("residual_share", "Remaining Balance Share"), c("total_share", "Total Share"),
            c("posted_entitlement", "Posted Entitlement"), c("pending_entitlement", "Pending Entitlement"),
            c("cash_paid", "Partner Payments"), c("adjustments", "Other Partner Adjustments"),
            c("outstanding_amount", "Outstanding"), c("status", "Entitlement Status", "Data", None)]
    elif view == "Source Details":
        detail = [c("source_posting_date", "Source Posting Date", "Date", None, 130),
            c("source_doctype", "Source Type", "Link", "DocType"), c("source_name", "Source Document", "Dynamic Link", "source_doctype", 180),
            c("expense_type", "Expense Type", "Data", None), c("description", "Description", "Data", None, 260),
            c("revenue", "Allocated Revenue"), c("expenses", "Allocated Cost"),
            c("source_original_amount", "Source Amount (Reference)", "Data", None, 180),
            c("allocation_basis", "Allocation Basis", "Data", None, 180), c("income_account", "Income Account", "Link", "Account", 180),
            c("service_from_date", "Service From Date", "Date", None), c("service_to_date", "Service To Date", "Date", None)]
    else:
        detail = [c("shareholder", "Shareholder", "Link", "Shareholder"), c("partner_name", "Partner Name", "Data", None, 200),
            c("movement_date", "Movement Date", "Date", None), c("movement", "Movement", "Data", None),
            c("voucher_type", "Voucher Type", "Link", "DocType"), c("voucher_no", "Voucher", "Dynamic Link", "voucher_type", 180),
            c("increase", "Entitlement Increase"), c("decrease", "Settlement / Payment Decrease"),
            c("running_balance", "Partner Settlement Balance"), c("status", "Entitlement Status", "Data", None)]
    if view == "Participant Summary":
        common = [c("settlement_status", "Settlement Status", "Data", None), c("settlement_count", "Settlement Count", "Int", None, 120)]
        context = []
        detail = [col for col in detail if col["fieldname"] not in ("ownership_percentage", "profit_percentage")]
    return common + detail + context + [dict(fieldname="currency", fieldtype="Link", options="Currency", hidden=1)]
