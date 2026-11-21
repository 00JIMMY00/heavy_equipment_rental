"""Current crane shares and accounting source attribution.

All money remains in ERPNext. Settlement documents only control period closure,
operating priority and immutable evidence; they never create an extra ledger.
"""

import json
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, flt, get_last_day, getdate, today, now_datetime, get_first_day

from heavy_equipment_rental.rental_validation import lock_cranes


SHARING_TYPES = ("Shared Ownership", "Operated for Owner", "Operated by Partner")
OPERATING_FIRST = "Operating First"
LEGACY_NET = "Legacy Net Profit"


def allocate_amount(total, weights, precision):
    """Signed, deterministic largest-remainder allocation in currency units."""
    quantum = Decimal(1).scaleb(-precision)
    total = Decimal(str(flt(total, precision)))
    weights = [Decimal(str(w)) for w in weights]
    denominator = sum(weights)
    if not denominator:
        if total:
            frappe.throw(_("Cannot allocate a non-zero invoice Grand Total across zero net item amounts."))
        return [0.0 for w in weights]
    raw = [total * weight / denominator for weight in weights]
    amounts = [value.quantize(quantum, rounding=ROUND_FLOOR) for value in raw]
    remainder = int((total - sum(amounts)) / quantum)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - amounts[i], -i), reverse=True)
    for index in order[:remainder]:
        amounts[index] += quantum
    return [float(value) for value in amounts]


def install_fields():
    create_custom_fields({doctype: [{
        "fieldname": "crane", "fieldtype": "Link", "label": "Crane",
        "options": "Crane", "insert_after": after,
        "description": "Attribute this income or expense to a Crane for profit settlements.",
    }] for doctype, after in (("Journal Entry Account", "cost_center"),
                              ("Sales Invoice Item", "cost_center"),
                              ("Purchase Invoice Item", "cost_center"))})
    frappe.db.add_index("Crane Profit Settlement", ["crane", "docstatus", "to_date"],
                        "crane_settlement_period")


def dumps(value):
    return json.dumps(value, sort_keys=True, indent=2, default=str)


def percentage(value):
    try:
        number = Decimal(str(value or 0))
        if not number.is_finite() or not 0 <= number <= 100:
            raise ValueError
        return float(number.quantize(Decimal("0.000001")))
    except (InvalidOperation, ValueError):
        frappe.throw(_("Percentages must be finite numbers between 0 and 100."))


def validate_account(name, company, currency, *, payable=False):
    account = frappe.get_doc("Account", name)
    account.check_permission("read")
    if (account.company != company or account.is_group or account.disabled
            or account.account_currency != currency
            or (payable and account.account_type != "Payable")
            or (not payable and (account.root_type not in ("Expense", "Equity")
                                 or account.account_type in ("Payable", "Receivable")))):
        frappe.throw(_("Select enabled, non-group accounts in the agreement Company currency: "
                       "a Payable account for partners and an Expense or Equity allocation account."))


def revenue_dimensions(row, parent=None):
    from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

    return {field: row.get(field) or (parent.get(field) if parent else None)
            for field in ("cost_center", "project", *get_accounting_dimensions())}


def revenue_allocation_rows(sources, amount, company, currency, cost_center, precision):
    """Reduce the source income accounts, preserving signed returns and dimensions."""
    grouped = {}
    for source in sources:
        if not source.get("revenue"):
            continue
        account = source.get("income_account")
        if not account:
            frappe.throw(_("Revenue account is missing for {0}. Recalculate the settlement.").format(source["name"]))
        dimensions = dict(source.get("dimensions") or {})
        dimensions["cost_center"] = dimensions.get("cost_center") or cost_center
        key = (account, tuple(sorted(dimensions.items())))
        grouped[key] = grouped.get(key, 0) + source["revenue"]
    grouped = {key: value for key, value in grouped.items() if flt(value, precision)}
    keys = sorted(grouped, key=str)
    if not keys or flt(sum(grouped.values()), precision) <= 0:
        frappe.throw(_("A positive source revenue balance is required to allocate partner entitlements."))
    amounts = allocate_amount(amount, [grouped[key] for key in keys], precision)
    rows = []
    for (account_name, dimensions), value in zip(keys, amounts):
        if not value:
            continue
        account = frappe.get_doc("Account", account_name)
        account.check_permission("read")
        if (account.company != company or account.is_group or account.disabled
                or account.root_type != "Income" or account.account_currency != currency):
            frappe.throw(_("Revenue account {0} must be an enabled Income account in the settlement Company currency.").format(account_name))
        rows.append(dict(account=account_name, **dict(dimensions),
                         debit_in_account_currency=max(value, 0),
                         credit_in_account_currency=max(-value, 0)))
    return rows


def validate_agreement(doc):
    from heavy_equipment_rental.partner_accounts import default_account, modern_agreement

    if doc.sharing_company:
        doc.partner_payable_account = doc.partner_payable_account or default_account(doc.sharing_company)
        doc.sharing_cost_center = doc.sharing_cost_center or frappe.get_cached_value("Company", doc.sharing_company, "cost_center")
    before = doc.get_doc_before_save()
    history = json.loads(before.agreement_history or "[]") if before else []
    if (doc.agreement_history or "") != (before.agreement_history or "" if before else ""):
        frappe.throw(_("Agreement History is maintained automatically."))
    doc.settlement_revenue_basis = doc.get("settlement_revenue_basis") or (
        history[-1].get("settlement_revenue_basis", "Invoice Grand Total") if history else "Invoice Grand Total")
    if not doc.enable_profit_sharing and not history:
        return
    if history and doc.sharing_company != history[0]["company"]:
        frappe.throw(_("The agreement Company cannot change after an agreement is recorded."))
    version = dict(enabled=bool(doc.enable_profit_sharing), company=doc.sharing_company,
                   ownership_type=doc.ownership_type, operator_type=doc.operator_type,
                   operating_partner=doc.operating_partner or None,
                   operating_shareholder=doc.operating_shareholder or None,
                   allocation_account=doc.profit_allocation_account,
                   payable_account=doc.partner_payable_account, cost_center=doc.sharing_cost_center,
                   partners=[])
    version.update(calculation_method=doc.sharing_calculation or OPERATING_FIRST,
                   operating_percentage=percentage(doc.operating_percentage),
                   settlement_approval=doc.settlement_approval or "On Invoice Submission",
                   distribution_posting=doc.distribution_posting or "Source Revenue Accounts",
                   include_depreciation=int(bool(doc.include_depreciation)),
                   settlement_revenue_basis=doc.settlement_revenue_basis)
    if version["calculation_method"] not in (OPERATING_FIRST, LEGACY_NET):
        frappe.throw(_("Invalid agreement calculation method."))
    if doc.enable_profit_sharing:
        if not all((doc.sharing_company, doc.partner_payable_account, doc.sharing_cost_center)):
            frappe.throw(_("Set the agreement Company, payable account and cost center."))
        company = frappe.get_doc("Company", doc.sharing_company)
        company.check_permission("read")
        version["currency"] = company.default_currency
        if version["calculation_method"] == LEGACY_NET or version["distribution_posting"] != "Source Revenue Accounts":
            validate_account(doc.profit_allocation_account, company.name, company.default_currency)
        if version["calculation_method"] != LEGACY_NET and version["distribution_posting"] != "Source Revenue Accounts":
            root = "Equity" if version["distribution_posting"] == "Equity Distribution" else "Expense"
            if frappe.get_cached_value("Account", doc.profit_allocation_account, "root_type") != root:
                frappe.throw(_("Partner Allocation Account must be an {0} account for this treatment.").format(root))
        validate_account(doc.partner_payable_account, company.name, company.default_currency, payable=True)
        center = frappe.get_doc("Cost Center", doc.sharing_cost_center)
        if center.company != company.name or center.is_group or center.disabled:
            frappe.throw(_("Select an enabled, non-group Cost Center in the agreement Company."))
        seen = set()
        for row in doc.ownership_partners:
            if not row.is_company and not row.shareholder and row.supplier:
                from heavy_equipment_rental.partner_accounts import shareholder_for_supplier
                row.shareholder = shareholder_for_supplier(row.supplier, company.name)
            key = "company" if row.is_company else row.shareholder
            if not key or key in seen:
                frappe.throw(_("Include our Company once and each external Supplier once."))
            seen.add(key)
            if row.is_company:
                row.supplier = row.shareholder = None
            else:
                partner = frappe.get_doc("Shareholder", row.shareholder)
                partner.check_permission("read")
                if partner.company != company.name:
                    frappe.throw(_("Partner Shareholders must belong to the agreement Company."))
                row.supplier = partner.crane_partner_supplier or None
            row.ownership_percentage = percentage(row.ownership_percentage)
            row.profit_percentage = percentage(row.profit_percentage)
            version["partners"].append(dict(is_company=int(bool(row.is_company)), supplier=row.supplier or None,
                shareholder=row.shareholder or None,
                ownership_percentage=row.ownership_percentage, profit_percentage=row.profit_percentage))
            if row.get("allow_zero_profit_share") and row.ownership_percentage > 0 and not row.profit_percentage:
                version["partners"][-1]["allow_zero_profit_share"] = 1
        for field in ("ownership_percentage", "profit_percentage"):
            if sum(Decimal(str(p[field])) for p in version["partners"]) != 100:
                frappe.throw(_("Ownership percentages and Profit Share percentages must each total 100%."))
    from heavy_equipment_rental.operating_fees import validate_rows, canonical_rows, agreement_rows
    fee_rows = validate_rows(doc)
    version['operating_fees'] = fee_rows
    if version['distribution_posting'] == 'Equity Distribution' and any(not r['is_company'] and r['percentage'] for r in fee_rows):
        frappe.throw(_("External operator fees cannot use Equity Distribution."))
    previous = {k: v for k, v in history[-1].items() if k not in ("effective_from", "recorded_at")} if history else None
    if previous:
        previous.setdefault("calculation_method", LEGACY_NET)
        previous.setdefault("operating_percentage", 0)
        previous.setdefault("settlement_approval", "On Invoice Submission")
        previous.setdefault("distribution_posting", "Source Revenue Accounts")
        previous.setdefault("include_depreciation", 0)
        previous.setdefault("settlement_revenue_basis", "Invoice Grand Total")
        previous = modern_agreement(previous)
        previous.setdefault("operating_shareholder", None)
        for p in previous["partners"]:
            p.setdefault("shareholder", None)
        # The migration changes the current default ledger only. Dated snapshots stay intact.
        if before and before.partner_payable_account == doc.partner_payable_account:
            previous["payable_account"] = before.partner_payable_account
    if previous and 'operating_fees' not in previous:
        old_rows = agreement_rows(previous)
        for row in old_rows:
            row['basis'] = 'Grand Total'
        previous['operating_fees'] = canonical_rows(old_rows)
    if version == previous:
        return
    frappe.only_for(("Accounts Manager", "System Manager"))
    if doc.enable_profit_sharing:
        for row in doc.ownership_partners:
            if row.ownership_percentage > 0 and not row.profit_percentage and not row.get("allow_zero_profit_share"):
                frappe.throw(_("Row {0}: this owner has {1}% ownership but 0% Remaining Balance. "
                    "Enter their agreed profit share, or select Confirm Owner Receives No Remaining Profit "
                    "only if this is intentional. Ownership % does not determine payment by itself.").format(
                        row.idx, row.ownership_percentage), title=_("Owner Has No Profit Share"))
    if version["calculation_method"] != OPERATING_FIRST:
        frappe.throw(_("Changed agreements must use Operating First. Review the profit-sharing terms before saving."))
    history.append(dict(recorded_at=str(now_datetime()), **version))
    doc.agreement_history = dumps(history)


def last_settlement(crane):
    rows = frappe.get_all("Crane Profit Settlement", filters={"crane": crane, "docstatus": 1, "settlement_basis": ["!=", "Timesheet"]},
        fields=["name", "to_date", "loss_carried_forward"], order_by="to_date desc", limit=1)
    return rows[0] if rows else None


def next_period_start(crane, previous=None):
    agreement_for(crane, None, None)
    return getdate(add_days(previous.to_date, 1)) if previous else get_first_day(today())


def agreement_for(crane, start=None, end=None):
    # Dates identify work, never select ownership or profit-share versions.
    history = json.loads(crane.agreement_history or "[]")
    if not crane.enable_profit_sharing or not history or not history[-1]["enabled"]:
        frappe.throw(_("Configure and enable profit sharing on the Crane first."))
    return {key: value for key, value in history[-1].items()
            if key not in ("effective_from", "recorded_at")}


@frappe.whitelist()
def settlement_defaults(crane):
    doc = frappe.get_doc("Crane", crane)
    doc.check_permission("read")
    frappe.has_permission("Crane Profit Settlement", "create", throw=True)
    start = next_period_start(doc, last_settlement(crane))
    end = max(start, min(get_last_day(start), getdate(today())))
    return dict(crane=crane, company=doc.sharing_company, from_date=str(start), to_date=str(end))


def invoice_cranes(doc):
    """All rental links, including returns and pre-existing untagged invoices."""
    link = "sales_invoice" if doc.doctype == "Sales Invoice" else "purchase_invoice"
    names = list(filter(None, [doc.name, doc.get("return_against")]))
    mapping = {}
    for sheet in frappe.get_all("Crane Timesheet", filters={link: ["in", names], "docstatus": 1},
                                fields=["crane"]):
        item = frappe.db.get_value("Crane", sheet.crane, "item")
        mapping.setdefault(item, set()).add(sheet.crane)
    return mapping


def source_cranes(doc):
    if doc.doctype in ("Expense Entry", "Stock Entry", "Asset Repair"):
        return {doc.crane} if doc.crane else set()
    if doc.doctype == "Journal Entry":
        if doc.voucher_type == "Depreciation Entry" and doc.finance_book and doc.finance_book != frappe.get_cached_value("Company", doc.company, "default_finance_book"):
            return set()
        cranes = {r.crane for r in doc.accounts if r.get("crane") and
                  frappe.get_cached_value("Account", r.account, "root_type") in ("Income", "Expense")}
        cranes.update(frappe.get_all("Expense Entry", filters={"journal_entry": doc.name, "docstatus": 1},
                                     pluck="crane"))
        return set(filter(None, cranes))
    mapping = invoice_cranes(doc)
    cranes = set().union(*mapping.values()) if mapping else set()
    for row in doc.items:
        if not row.get("crane") or row.get("is_fixed_asset"):
            continue
        if doc.doctype == "Purchase Invoice" and (
                frappe.get_cached_value("Item", row.item_code, "is_stock_item") or
                frappe.get_cached_value("Account", row.expense_account, "root_type") != "Expense"):
            continue
        if row.item_code in mapping and row.crane not in mapping[row.item_code]:
            frappe.throw(_("Invoice Crane attribution conflicts with its rental Timesheets."))
        cranes.add(row.crane)
    return cranes


def guard_closed_period(doc, method=None):
    """Serialize source posting with settlements, and keep closed periods stable."""
    if doc.get("crane_maintenance"):
        from heavy_equipment_rental.crane_repairs import guard_repair_posting
        guard_repair_posting(doc, method)
        if frappe.db.get_value("Crane Maintenance", doc.crane_maintenance, "cost_treatment") != "Operating Expense":
            return
    if doc.doctype == "Journal Entry":
        active = frappe.db.get_value("Crane Profit Settlement", {"journal_entry": doc.name, "docstatus": 1}, "name")
        if active:
            if method == "before_submit":
                # Only the settlement controller registers this read-only link,
                # after locking/recalculating and before submitting its journal.
                return
            frappe.throw(_("Cancel Crane Profit Settlement {0} to reverse its Journal Entry.").format(active))
    cranes = source_cranes(doc)
    lock_cranes(cranes)
    from heavy_equipment_rental.timesheet_settlement import guard_source_snapshots
    guard_source_snapshots(doc, cranes)
    if doc.get("crane_maintenance"):
        return  # Repair attribution and captured historical sources were checked above.
    if doc.doctype == "Expense Entry":
        from heavy_equipment_rental.rental_expenses import guard_expense
        guard_expense(doc)
        return
    if doc.doctype == "Journal Entry":
        from heavy_equipment_rental.consolidated_accounting import guard_journal
        if guard_journal(doc):
            return
        expense_name = frappe.db.get_value("Expense Entry", {"journal_entry": doc.name, "docstatus": ["in", [1, 2]]}, "name")
        if expense_name:
            from heavy_equipment_rental.rental_expenses import guard_expense
            guard_expense(frappe.get_doc("Expense Entry", expense_name))
            return
    for crane in sorted(cranes):
        agreement_company, history = frappe.db.get_value("Crane", crane,
                                                        ["sharing_company", "agreement_history"])
        if history and agreement_company and agreement_company != doc.company:
            frappe.throw(_("Crane {0} belongs to another agreement Company.").format(crane))
        closed = frappe.db.get_value("Crane Profit Settlement", {
            "crane": crane, "company": doc.company, "docstatus": 1,
            "settlement_basis": ["!=", "Timesheet"],
            "from_date": ["<=", doc.posting_date], "to_date": [">=", doc.posting_date],
        }, "name")
        if closed:
            frappe.throw(_("Period closed by {0}. Cancel later settlements first, or post the adjustment "
                           "in an open period.").format(closed))
        if doc.doctype in ("Expense Entry", "Journal Entry", "Purchase Invoice", "Stock Entry"):
            closed_work = frappe.db.get_value("Crane Profit Settlement", {
                "crane": crane, "company": doc.company, "docstatus": 1, "settlement_basis": "Timesheet",
                "from_date": ["<=", doc.posting_date], "to_date": [">=", doc.posting_date]}, "name")
            if closed_work:
                frappe.throw(_("Work costs are closed by settlement {0}. Cancel the settlement first.").format(closed_work))


def attributed_journals(cranes, company, start, end):
    """Read eligible postings once for the requested fleet and posting period."""
    if not cranes:
        return
    rows = frappe.db.sql("""
        SELECT j.name, a.name AS detail
        FROM `tabJournal Entry` j JOIN `tabJournal Entry Account` a ON a.parent=j.name
        JOIN `tabAccount` account ON account.name=a.account AND account.root_type IN ('Income','Expense')
        WHERE j.company=%s AND j.docstatus=1 AND j.posting_date BETWEEN %s AND %s
          AND a.crane IN %s
          AND NOT EXISTS (SELECT 1 FROM `tabExpense Entry` e WHERE e.journal_entry=j.name
                          AND e.docstatus=1 AND e.company=j.company AND e.crane=a.crane)
          AND NOT EXISTS (SELECT 1 FROM `tabGrouped Expense Item` i JOIN `tabGrouped Expense` b
                          ON b.name=i.parent WHERE i.journal_entry=j.name AND b.docstatus=1
                          AND b.company=j.company AND b.crane=a.crane)
          AND NOT EXISTS (SELECT 1 FROM `tabCrane Profit Settlement` s
                          WHERE s.docstatus=1 AND s.journal_entry=j.name)
        """, (company, start, end, tuple(cranes)))
    by_journal = {}
    for name, detail in rows:
        by_journal.setdefault(name, set()).add(detail)
    for name, details in by_journal.items():
        journal = frappe.get_doc("Journal Entry", name)
        if journal.voucher_type == "Depreciation Entry" and journal.finance_book and journal.finance_book != frappe.get_cached_value("Company", company, "default_finance_book"):
            continue
        for row in journal.accounts:
            if row.name not in details:
                continue
            root = frappe.get_cached_value("Account", row.account, "root_type")
            if root not in ("Income", "Expense"):
                continue
            journal.check_permission("read")
            value = flt(row.credit) - flt(row.debit) if root == "Income" else flt(row.debit) - flt(row.credit)
            yield row.crane, dict(doctype="Journal Entry", name=name, detail=row.name,
                posting_date=str(journal.posting_date),
                is_depreciation=journal.voucher_type == "Depreciation Entry",
                **(dict(income_account=row.account, dimensions=revenue_dimensions(row)) if root == "Income" else {}),
                **{"revenue" if root == "Income" else "expenses": value})


def collect_sources(crane, company, start, end, *, grand_total=False, include_expenses=True):
    """Accrual margin in company currency; explicit crane allocation only.

    Fetch complete candidates and check document permissions individually: an
    inaccessible source must fail a settlement, never silently reduce its profit.
    """
    for doctype in ("Crane Timesheet", "Sales Invoice", "Purchase Invoice", "Expense Entry", "Journal Entry"):
        frappe.has_permission(doctype, "read", throw=True)
    dates = ["between", [start, end]]
    sources = []
    for doctype, side in (("Sales Invoice", "revenue"), ("Purchase Invoice", "expenses")):
        link = "sales_invoice" if doctype == "Sales Invoice" else "purchase_invoice"
        links = list(filter(None, frappe.get_all("Crane Timesheet", filters={"crane": crane, "docstatus": 1}, pluck=link)))
        # Only load candidate headers, rather than every invoice in the company.
        candidates = frappe.get_all(doctype, filters={"company": company, "docstatus": 1,
            "posting_date": dates}, or_filters=[
                [doctype, "name", "in", links], [doctype, "return_against", "in", links],
                [doctype + " Item", "crane", "=", crane],
            ], pluck="name", distinct=True)
        for name in candidates:
            invoice = frappe.get_doc(doctype, name)
            mapping = invoice_cranes(invoice)
            relevant = any(r.get("crane") == crane or (not r.get("crane") and crane in mapping.get(r.item_code, set()))
                           for r in invoice.items)
            if not relevant:
                continue
            invoice.check_permission("read")
            amounts = ([flt(r.base_net_amount) for r in invoice.items]
                       if not grand_total or doctype != "Sales Invoice" else
                       allocate_amount(invoice.base_grand_total,
                                       [r.base_net_amount for r in invoice.items],
                                       invoice.precision("base_grand_total")))
            if (grand_total and doctype == "Sales Invoice" and not invoice.base_grand_total
                    and not sum(flt(r.base_net_amount) for r in invoice.items)):
                # A zero-value invoice may transfer value between two cranes
                # with opposite signed items; keep that explicit attribution.
                amounts = [flt(r.base_net_amount) for r in invoice.items]
            for row, amount in zip(invoice.items, amounts):
                # Stock purchases and improvements are not rental operating costs.
                if invoice.get("crane_maintenance"):
                    continue  # Native repair costs are collected once from their actual ledger.
                if row.get("is_fixed_asset"):
                    continue
                if doctype == "Purchase Invoice" and (
                        frappe.get_cached_value("Item", row.item_code, "is_stock_item") or
                        frappe.get_cached_value("Account", row.expense_account, "root_type") != "Expense"):
                    continue
                linked = {row.crane} if row.get("crane") else mapping.get(row.item_code, set())
                if crane not in linked:
                    continue
                if len(linked) != 1:
                    frappe.throw(_("Invoice {0} has ambiguous Crane links.").format(name))
                sources.append(dict(doctype=doctype, name=name, detail=row.name,
                                    posting_date=str(invoice.posting_date),
                                    basis="Grand Total allocation" if grand_total and doctype == "Sales Invoice" else "Net item amount",
                                    **(dict(income_account=row.income_account,
                                            dimensions=revenue_dimensions(row, invoice))
                                       if doctype == "Sales Invoice" else {}),
                                    **{side: amount}))
    from heavy_equipment_rental.rental_expenses import expense_sources, check_posted
    if include_expenses:
        for expense, source in expense_sources(crane, company):
            first, last = getdate(source["service_from_date"]), getdate(source["service_to_date"])
            overlap = (min(getdate(end), last) - max(getdate(start), first)).days + 1
            if overlap <= 0:
                continue
            check_posted(expense)
            total = source["expenses"]
            days = (last - first).days + 1
            source["source_amount"] = total
            source["allocation_from_date"] = str(max(getdate(start), first))
            source["allocation_to_date"] = str(min(getdate(end), last))
            # Allocate rounding cents to fixed calendar dates so separate period
            # settlements cannot each receive the same rounding remainder.
            daily = allocate_amount(total, [1] * days,
                frappe.get_precision("Crane Profit Settlement", "revenue", currency=frappe.get_cached_value("Company", company, "default_currency")))
            offset = (max(getdate(start), first) - first).days
            source["expenses"] = flt(sum(daily[offset:offset + overlap]),
                frappe.get_precision("Crane Profit Settlement", "revenue", currency=frappe.get_cached_value("Company", company, "default_currency")))
            sources.append(source)
    sources.extend(source for _, source in attributed_journals([crane], company, start, end))
    if include_expenses:
        from heavy_equipment_rental.crane_repairs import repair_expense_sources, allocate_repair_period
        for source in repair_expense_sources(crane, company):
            if allocated := allocate_repair_period(source, company, start, end):
                sources.append(allocated)
    return sorted(sources, key=lambda r: (r["posting_date"], r["doctype"], r["name"], r.get("detail", "")))
