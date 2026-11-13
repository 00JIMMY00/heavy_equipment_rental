"""A cash/custody account statement in the source workbook's seven columns."""

from collections import defaultdict
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction import is_treasury_account


METADATA = ["her_workbook_batch", "her_workbook_row", "her_workbook_date", "her_workbook_name", "her_workbook_category"]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not all(filters.get(key) for key in ("company", "account", "from_date", "to_date")):
        frappe.throw(_("Company, Account, From Date and To Date are required."))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date must be before To Date."))
    frappe.get_doc("Company", filters.company).check_permission("read")
    account = frappe.get_doc("Account", filters.account)
    account.check_permission("read")
    currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    if (account.company != filters.company or account.is_group or account.disabled
            or account.account_currency != currency or not is_treasury_account(account)):
        frappe.throw(_("Select an enabled treasury/custody account in this Company's currency."))
    if filters.cost_center:
        center = frappe.get_doc("Cost Center", filters.cost_center)
        center.check_permission("read")
        if center.company != filters.company or center.is_group or center.disabled:
            frappe.throw(_("Select an enabled, non-group Cost Center for this Company."))
    for doctype in ("GL Entry", "Journal Entry", "Expense Entry", "Treasury Transaction"):
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Read permission for {0} is required for this report.").format(doctype), frappe.PermissionError)

    # Use permission-aware GL selection. Posted journals are the accounting source;
    # a cancelled source cannot reappear through stale workbook metadata.
    ledger = frappe.get_list("GL Entry", filters={
        "company": filters.company, "account": filters.account, "is_cancelled": 0,
        "posting_date": ["<=", filters.to_date],
    }, fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit", "against", "cost_center"],
        limit_page_length=0, order_by="posting_date, creation, name")
    grouped = {}
    for entry in ledger:
        key = (entry.voucher_type, entry.voucher_no)
        if key not in grouped:
            grouped[key] = dict(posting_date=entry.posting_date, incoming=0, outgoing=0,
                                against=entry.against, cost_center=entry.cost_center, entries=[])
        grouped[key]["entries"].append(entry)
        grouped[key]["incoming"] += flt(entry.debit)
        grouped[key]["outgoing"] += flt(entry.credit)

    sources = defaultdict(list)
    # Map only journals actually present in the selected ledger. Checking the
    # linked source document enforces both role and document-level restrictions.
    journals = [number for kind, number in grouped if kind == "Journal Entry"]
    if journals:
        for doctype in ("Expense Entry", "Treasury Transaction"):
            for header in frappe.get_all(doctype, filters={"company": filters.company, "journal_entry": ["in", journals]},
                                         fields=["name", "journal_entry"]):
                sources[header.journal_entry].append((doctype, header.name))
    opening, data = 0, []
    for (kind, number), amounts in grouped.items():
        document = frappe.get_doc(kind, number)
        document.check_permission("read")
        if document.docstatus != 1 or document.get("company") != filters.company:
            continue
        source = document
        linked = sources.get(number, []) if kind == "Journal Entry" else []
        if len(linked) > 1:
            frappe.throw(_("Journal {0} has multiple source documents. Review it before reporting.").format(number))
        if linked:
            source = frappe.get_doc(*linked[0])
            source.check_permission("read")
            if source.docstatus != 1:
                continue
        if filters.batch and source.get("her_workbook_batch") != filters.batch:
            continue
        # Expense/transfer headers retain the business dimension even when native
        # ERPNext omits Cost Center from balance-sheet GL rows. Ordinary vouchers
        # filter their actual selected-account GL rows, without inferring a split
        # from expense counterparties in a journal with multiple cost centers.
        source_center = source.get("cost_center") if linked else None
        if filters.cost_center:
            if source_center:
                if source_center != filters.cost_center:
                    continue
            else:
                matching = [entry for entry in amounts["entries"] if entry.cost_center == filters.cost_center]
                if not matching:
                    continue
                amounts = dict(amounts, incoming=sum(flt(e.debit) for e in matching),
                               outgoing=sum(flt(e.credit) for e in matching), cost_center=filters.cost_center)
        if getdate(amounts["posting_date"]) < getdate(filters.from_date):
            opening += amounts["incoming"] - amounts["outgoing"]
            continue
        data.append(dict(
            posting_date=amounts["posting_date"],
            display_date=(source.get("her_workbook_date") or "") if source.get("her_workbook_batch")
                else getdate(amounts["posting_date"]).strftime("%d/%m/%Y"),
            incoming=flt(amounts["incoming"], 2), outgoing=flt(amounts["outgoing"], 2),
            party_name=source.get("her_workbook_name") or document.get("party_name") or amounts["against"] or "",
            category=source.get("her_workbook_category") or source_center or amounts["cost_center"] or "",
            cost_center=source_center or amounts["cost_center"] or "",
            description=source.get("description") or document.get("user_remark") or document.get("remarks") or "",
            voucher_type=source.doctype, voucher=source.name, journal=number if kind == "Journal Entry" else "",
            batch=source.get("her_workbook_batch") or "", sheet_row=cint(source.get("her_workbook_row")), currency=currency,
        ))
    if filters.batch and cint(filters.workbook_order):
        data.sort(key=lambda r: (r["sheet_row"], r["voucher"]))
    else:
        data.sort(key=lambda r: (getdate(r["posting_date"]), r["sheet_row"], r["voucher"]))
    balance = flt(opening, 2)
    incoming = outgoing = 0
    if opening:
        data.insert(0, dict(display_date="", description=_("Opening Balance"), incoming=0, outgoing=0,
                            currency=currency, is_opening=1))
    for row in data:
        incoming += row["incoming"]
        outgoing += row["outgoing"]
        balance = flt(balance + row["incoming"] - row["outgoing"], 2)
        row["balance"] = balance
    summary = [dict(label=label, value=value, datatype="Currency", currency=currency) for label, value in (
        (_("Opening Balance"), flt(opening, 2)), ("الوارد", incoming), ("المنصرف", outgoing), ("الرصيد", balance))]
    message = _("Posted ledger movements only. Select one treasury, custody, employee advance or current account. "
                "Workbook order reproduces the original rows; posting dates remain available in source documents. "
                "Employee advances and owner drawings are balance-sheet movements, not operating expenses.")
    if filters.cost_center:
        message += " " + _("Balances and totals apply only to the selected Cost Center.")
    return columns(), data, message, None, summary


def columns():
    return [
        dict(fieldname="display_date", label="التاربخ", fieldtype="Data", width=110),
        *[dict(fieldname=field, label=label, fieldtype="Currency", options="currency", width=125)
          for field, label in (("incoming", "الوارد"), ("outgoing", "المنصرف"), ("balance", "الرصيد"))],
        dict(fieldname="party_name", label="الإسم", fieldtype="Data", width=180),
        dict(fieldname="category", label="مركز التكلفة", fieldtype="Data", width=210),
        dict(fieldname="description", label="البيان", fieldtype="Data", width=500),
        dict(fieldname="voucher_type", label=_("Document Type"), fieldtype="Data", hidden=1),
        dict(fieldname="voucher", label=_("Document"), fieldtype="Dynamic Link", options="voucher_type", hidden=1),
        dict(fieldname="currency", label=_("Currency"), fieldtype="Data", hidden=1),
    ]


@frappe.whitelist()
def get_defaults(company=None):
    """Open the most recent accessible workbook without changing user defaults."""
    candidates = []
    for doctype in ("Expense Entry", "Treasury Transaction"):
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Read permission for {0} is required for this report.").format(doctype), frappe.PermissionError)
        conditions = {"docstatus": 1, "her_workbook_batch": ["!=", ""]}
        if company:
            conditions["company"] = company
        candidates.extend(frappe.get_list(doctype, filters=conditions,
            fields=["company", "her_workbook_batch", "creation"], order_by="creation desc", page_length=1))
    if not candidates:
        if company:
            document = frappe.get_doc("Company", company)
            document.check_permission("read")
            return dict(account=document.default_cash_account, batch="")
        return {}
    latest = max(candidates, key=lambda r: r.creation)
    document = frappe.get_doc("Company", latest.company)
    document.check_permission("read")
    account = frappe.get_doc("Account", document.default_cash_account)
    account.check_permission("read")
    dates = []
    for doctype in ("Expense Entry", "Treasury Transaction"):
        dates.extend(frappe.get_list(doctype, filters={"company": latest.company, "docstatus": 1,
            "her_workbook_batch": latest.her_workbook_batch}, pluck="posting_date", limit_page_length=0))
    return dict(company=latest.company, account=account.name, batch=latest.her_workbook_batch,
                from_date=min(dates), to_date=max(dates), workbook_order=1)


@frappe.whitelist()
def download_workbook(filters):
    """Export live accounting results using the original workbook's layout."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    filters = frappe.parse_json(filters)
    _, data, _, _, _ = execute(filters)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "ورقة1"
    sheet.sheet_view.rightToLeft = True
    sheet.merge_cells("A2:B2")
    sheet.merge_cells("A3:B3")
    sheet["A2"] = "حركة الخزينة"
    sheet["A3"] = "لسنة " + str(getdate(filters["to_date"]).year)
    widths = (12.109375, 15.6640625, 13.0, 16.0, 23.33203125, 25.6640625, 88.6640625)
    for index, (width, column) in enumerate(zip(widths, columns()[:7]), 1):
        sheet.column_dimensions[openpyxl.utils.get_column_letter(index)].width = width
        sheet.cell(5, index, column["label"])
    orange = PatternFill("solid", fgColor="F4B183")
    border = Border(left=Side(style="thin"), right=Side(style="thin"),
                    top=Side(style="thin"), bottom=Side(style="thin"))
    for index, row in enumerate(data, 7):
        for col, key in enumerate(("display_date", "incoming", "outgoing", "balance", "party_name", "category", "description"), 1):
            # Prevent workbook text (including descriptions/names) becoming formulas.
            value = row.get(key, "")
            cell = sheet.cell(index, col, value)
            if isinstance(value, str):
                cell.data_type = "s"
            cell.font = Font(name="Calibri", size=12, bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border
            if col in (2, 3, 4):
                cell.number_format = '#,##0.00;(#,##0.00);"-"'
            if col == 4:
                cell.fill = orange
        sheet.row_dimensions[index].height = 15.6
    for row in sheet.iter_rows(min_row=2, max_row=5):
        for cell in row:
            cell.font = Font(name="Calibri", size=12, bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if cell.row == 5:
                cell.fill = orange
                cell.border = border
    sheet.row_dimensions[2].height = sheet.row_dimensions[3].height = 21
    sheet.row_dimensions[5].height = 15.6
    sheet.freeze_panes = "A7"
    sheet.print_title_rows = "2:5"
    stream = BytesIO()
    workbook.save(stream)
    frappe.local.response.filename = "حركة الخزينة.xlsx"
    frappe.local.response.filecontent = stream.getvalue()
    frappe.local.response.type = "binary"
