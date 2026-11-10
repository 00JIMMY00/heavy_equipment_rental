"""Explicit, reviewed treasury workbook imports; never called by migration.

Workbook cells are data, never executable formulas or import instructions.
Dates and opening balances must be resolved by the operator before posting.
"""

import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


SOURCE_DOCTYPES = ("Expense Entry", "Treasury Transaction", "Journal Entry")
HEADERS = ("التاربخ", "الوارد", "المنصرف", "الرصيد", "الإسم", "مركز التكلفة", "البيان")


def install_fields():
    fields = []
    for name, label, kind in (
        ("her_workbook_batch", "Treasury Workbook Batch", "Data"),
        ("her_workbook_row", "Workbook Row", "Int"),
        ("her_workbook_date", "Original Workbook Date", "Data"),
        ("her_workbook_name", "Workbook Name", "Data"),
        ("her_workbook_category", "Workbook Cost Center", "Data"),
    ):
        fields.append(dict(fieldname=name, label=label, fieldtype=kind,
                           read_only=1, no_copy=1, hidden=1))
    create_custom_fields({doctype: fields for doctype in SOURCE_DOCTYPES})
    create_custom_fields({"Account": [dict(
        fieldname="her_treasury_kind", label="Treasury Balance Type", fieldtype="Select",
        options="\nCustody\nEmployee Advance\nOwner Current", insert_after="account_type",
        description="Explicitly allow a company-currency custody, employee advance or current account in Treasury Transactions.",
    )]})


def money(value):
    if value in (None, ""):
        return Decimal("0.00")
    if isinstance(value, bool):
        raise ValueError("Boolean amounts are invalid")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid amount: " + str(value)) from exc
    if not result.is_finite() or result < 0 or result != result.quantize(Decimal("0.01")):
        raise ValueError("Amounts must be finite, nonnegative and use at most two decimal places")
    return result.quantize(Decimal("0.01"))


def inspect_workbook(path):
    """Read amounts without evaluating formulas; flag every ambiguous date."""
    import openpyxl

    path = Path(path)
    workbook = openpyxl.load_workbook(path, data_only=False)
    if len(workbook.worksheets) != 1:
        raise ValueError("Expected one worksheet")
    sheet = workbook.active
    if tuple(sheet.cell(5, i).value for i in range(1, 8)) != HEADERS:
        raise ValueError("Unexpected workbook columns")
    opening = sheet["D6"].value
    if opening is not None:
        opening = money(opening)
    balance = opening or Decimal("0.00")
    rows, issues = [], []
    previous_date = None
    for number in range(7, sheet.max_row + 1):
        values = [sheet.cell(number, i).value for i in range(1, 8)]
        if all(values[i] is None for i in (0, 1, 2, 4, 5, 6)):
            continue  # Ignore formatted/formula-only trailing rows.
        incoming, outgoing = money(values[1]), money(values[2])
        if (incoming > 0) == (outgoing > 0):
            raise ValueError(f"Row {number}: expected exactly one positive incoming/outgoing amount")
        formula = values[3]
        expected = f"=D{number - 1}+B{number}-C{number}"
        if formula != expected:
            raise ValueError(f"Row {number}: unexpected running-balance formula")
        raw_date = values[0]
        if isinstance(raw_date, (date, datetime)):
            # Preserve Excel's actual stored value; never silently flip it.
            proposed_date = raw_date.strftime("%Y-%m-%d")
            original_date = raw_date.strftime("%d/%m/%Y")
            issues.append(dict(row=number, issue="excel_date_requires_review", value=original_date))
        elif raw_date:
            proposed_date = datetime.strptime(str(raw_date).strip(), "%d/%m/%Y").date().isoformat()
            original_date = str(raw_date)
        else:
            proposed_date = previous_date
            original_date = ""
            issues.append(dict(row=number, issue="missing_date", proposed_date=proposed_date))
        previous_date = proposed_date
        if any(not isinstance(values[i], str) or not values[i].strip() for i in (4, 5, 6)):
            raise ValueError(f"Row {number}: name, category and description are required")
        balance += incoming - outgoing
        rows.append(dict(row=number, original_date=original_date, proposed_date=proposed_date,
                         incoming=float(incoming), outgoing=float(outgoing), balance=float(balance),
                         party_name=values[4], category=values[5], description=values[6]))
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), sheet=sheet.title,
                opening_balance=None if opening is None else float(opening), rows=rows, issues=issues,
                totals=dict(incoming=float(sum(money(r["incoming"]) for r in rows)),
                            outgoing=float(sum(money(r["outgoing"]) for r in rows)),
                            closing_balance=float(balance)))


def source_fields(batch, row):
    return dict(her_workbook_batch=batch, her_workbook_row=row["row"],
                her_workbook_date=row["original_date"], her_workbook_name=row["party_name"],
                her_workbook_category=row["category"])


def resolved_workbook(path):
    """The user's approved rules for this specific workbook, recorded in the audit."""
    inspection = inspect_workbook(path)
    previous = None
    for row in inspection["rows"]:
        value = row["proposed_date"] if row["original_date"] else previous
        if row["original_date"]:
            value = {"2026-12-10": "2026-10-12", "2026-06-10": "2026-10-06"}.get(value, value)
        if not value:
            raise ValueError(f"Row {row['row']}: no date available")
        row["posting_date"] = value
        row["display_date"] = datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y") if row["original_date"] else ""
        previous = value
        row["kind"] = ("funding" if row["incoming"] else
                       "advance" if row["category"].strip() == "سلفة" else
                       "owner_drawing" if row["category"].strip() in ("خزينه", "شخصي محمد خيري") else "expense")
    return inspection


def import_libya_workbook(path, company="شركة المعدات الثقيلة - ليبيا", abbr="HER-LY", expected_sha256=None):
    """Post the reviewed workbook atomically using normal native controllers.

    Approved starting balances are zero: no fictional opening journal is made.
    This explicit command does not delete any company's transactions.
    """
    frappe.only_for("System Manager")
    inspection = resolved_workbook(path)
    if expected_sha256 and inspection["sha256"] != expected_sha256:
        raise ValueError("Workbook changed after review")
    batch = "HER-" + inspection["sha256"][:20]
    existing = []
    for doctype in SOURCE_DOCTYPES:
        existing.extend(frappe.get_all(doctype, filters={"company": company, "her_workbook_batch": batch}, pluck="name"))
    if existing:
        return reconcile_workbook(path, company, batch)
    frappe.db.savepoint("her_workbook_import")
    try:
        if frappe.db.exists("Company", company):
            settings = frappe.get_doc("Company", company)
            if settings.default_currency != "LYD":
                raise ValueError("The import company must use LYD")
            if frappe.db.count("GL Entry", {"company": company}):
                raise ValueError("A first import requires an empty company ledger and approved zero opening balances")
        else:
            settings = frappe.get_doc(dict(doctype="Company", company_name=company, abbr=abbr,
                default_currency="LYD", country="Libya", create_chart_of_accounts_based_on="Standard Template",
                chart_of_accounts="Standard")).insert()
            settings.reload()
        accounts, modes, types, centers = _prepare_accounts(settings, inspection["rows"])
        for row in inspection["rows"]:
            fields = source_fields(batch, row)
            fields["her_workbook_date"] = row["display_date"]
            if row["kind"] == "expense":
                document = frappe.get_doc(dict(doctype="Expense Entry", company=company,
                    posting_date=row["posting_date"], mode_of_payment=modes["cash"],
                    cost_center=centers[row["category"]], description=row["description"],
                    expenses=[dict(expense_entry_type=types[row["category"]], amount=row["outgoing"])], **fields))
            else:
                source = "cash"
                if row["kind"] == "funding":
                    party = row["party_name"].strip()
                    source = "bank" if party == "مصرف" else "owner" if party == "الحاج / محمد خيري" else "current:" + party
                    destination = "cash"
                elif row["kind"] == "advance":
                    destination = "advance:" + row["party_name"].strip()
                else:
                    destination = "owner"
                document = frappe.get_doc(dict(doctype="Treasury Transaction", company=company,
                    posting_date=row["posting_date"], mode_of_payment=modes[source],
                    cost_center=centers[row["category"]],
                    destination_account=accounts[destination], amount=row["incoming"] or row["outgoing"],
                    reference_no=f"{batch}/{row['row']}", reference_date=row["posting_date"],
                    description=row["description"], **fields))
            document.insert()
            document.submit()
        result = reconcile_workbook(path, company, batch)
    except Exception:
        frappe.db.rollback(save_point="her_workbook_import")
        raise
    return result


def _prepare_accounts(company, rows):
    """Preserve source category spellings; don't infer crane IDs from similar labels."""
    parents = {}
    for key, filters in (
        ("cash", {"account_type": "Cash", "is_group": 1}),
        ("bank", {"account_type": "Bank", "is_group": 1}),
        ("asset", {"account_name": "Current Assets", "is_group": 1}),
        ("liability", {"account_name": "Current Liabilities", "is_group": 1}),
        ("expense", {"name": company.default_expense_account}),
    ):
        values = frappe.db.get_value("Account", dict(company=company.name, **filters), ["name", "parent_account"], as_dict=True)
        if not values:
            raise ValueError("Missing account parent: " + key)
        parents[key] = values.parent_account if key == "expense" else values.name
    accounts, modes = {}, {}

    def account(key, title, parent, account_type="", kind=""):
        existing = frappe.db.get_value("Account", {"company": company.name, "account_name": title}, "name")
        if existing:
            doc = frappe.get_doc("Account", existing)
            if (doc.parent_account != parents[parent] or doc.account_type != (account_type or None)
                    or doc.account_currency != "LYD" or doc.get("her_treasury_kind") != (kind or None)):
                # Empty string and None are both valid empty Select values.
                if (doc.parent_account != parents[parent] or (doc.account_type or "") != account_type
                        or doc.account_currency != "LYD" or (doc.get("her_treasury_kind") or "") != kind):
                    raise ValueError("Conflicting existing account: " + title)
        else:
            doc = frappe.get_doc(dict(doctype="Account", company=company.name, account_name=title,
                parent_account=parents[parent], account_currency="LYD", account_type=account_type,
                her_treasury_kind=kind)).insert()
        accounts[key] = doc.name
        return doc.name

    account("cash", "خزنة مرعي وائل", "cash", "Cash", "Custody")
    company.default_cash_account = accounts["cash"]
    company.save()
    account("bank", "المصرف - شيت الخزينة", "bank", "Bank")
    account("owner", "جاري محمد خيري", "liability", kind="Owner Current")
    for row in rows:
        party = row["party_name"].strip()
        if row["kind"] == "advance" and "advance:" + party not in accounts:
            account("advance:" + party, "سلف وعهد - " + party, "asset", kind="Employee Advance")
        if row["kind"] == "funding" and party not in ("مصرف", "الحاج / محمد خيري") and "current:" + party not in accounts:
            account("current:" + party, "جاري " + party, "liability", kind="Owner Current")
    for key, name in accounts.items():
        title = frappe.db.get_value("Account", name, "account_name") + " - " + company.abbr
        mode = frappe.db.get_value("Mode of Payment", title, "name")
        if not mode:
            mode = frappe.get_doc(dict(doctype="Mode of Payment", mode_of_payment=title,
                type="Bank" if key == "bank" else "Cash" if key == "cash" else "General", enabled=1,
                accounts=[dict(company=company.name, default_account=name)])).insert().name
        elif frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company.name}, "default_account") != name:
            raise ValueError("Conflicting existing payment mode: " + title)
        modes[key] = mode
    types, centers = {}, {}
    for category in sorted({r["category"] for r in rows if r["kind"] == "expense"}):
        expense_account = account("expense:" + category, "مصروف - " + category, "expense", "Expense Account")
        expense_type = frappe.db.get_value("Expense Entry Type", {"company": company.name, "title": category}, "name")
        if not expense_type:
            expense_type = frappe.get_doc(dict(doctype="Expense Entry Type", company=company.name,
                title=category, enabled=1, account=expense_account)).insert().name
        elif frappe.db.get_value("Expense Entry Type", expense_type, "account") != expense_account:
            raise ValueError("Conflicting existing expense type: " + category)
        types[category] = expense_type
    for category in sorted({r["category"] for r in rows}):
        centers[category] = ensure_workbook_cost_center(company, category)
    return accounts, modes, types, centers


def ensure_workbook_cost_center(company, category):
    center = frappe.db.get_value("Cost Center", {"company": company.name, "cost_center_name": category}, "name")
    if center:
        values = frappe.db.get_value("Cost Center", center, ["is_group", "disabled"], as_dict=True)
        if values.is_group or values.disabled:
            raise ValueError("Workbook Cost Center must be enabled and non-group: " + category)
        return center
    parent = frappe.db.get_value("Cost Center", company.cost_center, "parent_cost_center")
    if not parent:
        raise ValueError("Configure a default leaf Cost Center before importing workbook categories")
    return frappe.get_doc(dict(doctype="Cost Center", company=company.name, cost_center_name=category,
        parent_cost_center=parent, is_group=0)).insert().name


def reconcile_workbook(path, company, batch=None):
    """Fail unless every original row and every native GL posting reconciles."""
    from heavy_equipment_rental.heavy_equipment_rental.report.treasury_workbook.treasury_workbook import execute

    inspection = resolved_workbook(path)
    batch = batch or "HER-" + inspection["sha256"][:20]
    cash = frappe.db.get_value("Account", {"company": company, "account_name": "خزنة مرعي وائل"}, "name")
    if not cash:
        raise AssertionError("Workbook cash account is missing")
    dates = [r["posting_date"] for r in inspection["rows"]]
    _, rows, _, _, _ = execute(dict(company=company, account=cash, from_date=min(dates), to_date=max(dates),
                                    batch=batch, workbook_order=1))
    if len(rows) != len(inspection["rows"]):
        raise AssertionError("Workbook row count does not match posted ledger")
    journals = []
    counts = {}
    for actual, expected in zip(rows, inspection["rows"]):
        for key in ("incoming", "outgoing", "balance", "party_name", "category", "description"):
            if actual[key] != expected[key]:
                raise AssertionError(f"Row {expected['row']}: {key} mismatch: {actual[key]!r} != {expected[key]!r}")
        if actual["sheet_row"] != expected["row"] or str(actual["posting_date"]) != expected["posting_date"]:
            raise AssertionError("Row sequence or posting date mismatch")
        journal = frappe.get_doc("Journal Entry", actual["journal"])
        ledger = frappe.get_all("GL Entry", filters={"company": company, "voucher_type": "Journal Entry",
            "voucher_no": journal.name, "is_cancelled": 0}, fields=["account", "debit", "credit"])
        debit = sum(Decimal(str(r.debit)) for r in ledger)
        credit = sum(Decimal(str(r.credit)) for r in ledger)
        amount = money(expected["incoming"] or expected["outgoing"])
        if not ledger or debit != credit or debit != amount or journal.docstatus != 1:
            raise AssertionError("Unbalanced/missing/mismatched ledger for " + journal.name)
        if journal.name in journals:
            raise AssertionError("Duplicate source journal")
        journals.append(journal.name)
        counts[actual["voucher_type"]] = counts.get(actual["voucher_type"], 0) + 1
    balances = frappe.db.sql("""select account, sum(debit) - sum(credit) balance
        from `tabGL Entry` where company=%s and is_cancelled=0 group by account order by account""",
        (company,), as_dict=True)
    if sum(Decimal(str(r.balance)) for r in balances) != 0:
        raise AssertionError("Company trial balance does not balance")
    return dict(company=company, currency="LYD", batch=batch, sha256=inspection["sha256"], rows=len(rows),
                counts=counts, journals=len(journals), totals=inspection["totals"],
                opening_balances="All zero as approved; no zero-value journal posted", balances=balances,
                date_rules="Flip 2026-12-10 / 2026-06-10 only; fill blank dates from preceding resolved row",
                filters=dict(company=company, account=cash, from_date=min(dates), to_date=max(dates),
                             batch=batch, workbook_order=1))
