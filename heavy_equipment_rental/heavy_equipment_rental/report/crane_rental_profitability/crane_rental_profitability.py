"""Posted rental income and costs, in company currency and excluding invoice taxes."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import escape_html, flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not all(filters.get(key) for key in ("company", "from_date", "to_date")):
        frappe.throw(_("Company, From Date and To Date are required."))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date must be before To Date."))
    frappe.get_doc("Company", filters.company).check_permission("read")
    # Never return a plausible but incomplete profit because a source is inaccessible.
    for doctype in ("Crane Assignment", "Crane", "Crane Timesheet", "Sales Invoice",
                    "Purchase Invoice", "Expense Entry", "Journal Entry"):
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Read permission for {0} is required for this report.").format(doctype),
                         frappe.PermissionError)
    currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    assignments = frappe.get_list("Crane Assignment", filters={"company": filters.company},
                                  pluck="name", limit_page_length=0)
    if filters.assignment:
        assignments = [name for name in assignments if name == filters.assignment]
    cranes = frappe.get_list("Crane", fields=["name", "item"], limit_page_length=0)
    items = {row.name: row.item for row in cranes if not filters.crane or row.name == filters.crane}
    sheets = frappe.get_list("Crane Timesheet", filters={
        "docstatus": 1, "assignment": ["in", assignments], "crane": ["in", list(items)],
    }, fields=["name", "assignment", "crane", "sales_invoice", "purchase_invoice"], limit_page_length=0)
    data = []
    dates = ["between", [filters.from_date, filters.to_date]]
    for doctype, link, amount_field in (
        ("Sales Invoice", "sales_invoice", "income"),
        ("Purchase Invoice", "purchase_invoice", "expenses"),
    ):
        links = defaultdict(lambda: defaultdict(set))
        for sheet in sheets:
            if sheet.get(link):
                links[sheet.get(link)][items[sheet.crane]].add((sheet.assignment, sheet.crane))
        if not links:
            continue
        # Native credit/debit notes follow their original invoice, with signed amounts.
        invoices = frappe.get_list(doctype, filters={
            "docstatus": 1, "company": filters.company, "posting_date": dates,
        }, fields=["name", "return_against", "posting_date"], limit_page_length=0)
        for header in invoices:
            mapping = links.get(header.name) or links.get(header.return_against)
            if not mapping:
                continue
            invoice = frappe.get_doc(doctype, header.name)
            for line in invoice.items:
                sources = mapping.get(line.item_code)
                if not sources:
                    continue
                if len(sources) != 1:
                    frappe.throw(_("Invoice {0} has ambiguous rental links; review its Timesheets.").format(header.name))
                assignment, crane = next(iter(sources))
                data.append(dict(posting_date=header.posting_date, voucher_type=doctype,
                                 voucher=header.name, assignment=assignment, crane=crane,
                                 description=line.description, currency=currency,
                                 **{amount_field: flt(line.base_net_amount)}))
    expense_filters = {"docstatus": 1, "company": filters.company, "posting_date": dates}
    if filters.assignment:
        expense_filters["crane_assignment"] = ["in", assignments]
    if filters.crane:
        expense_filters["crane"] = filters.crane
    unposted_expenses = []
    for header in frappe.get_list("Expense Entry", filters=expense_filters,
                                  fields=["name", "crane", "crane_assignment"], limit_page_length=0):
        if header.crane_assignment and header.crane_assignment not in assignments:
            continue
        if header.crane and header.crane not in items:
            continue
        if not header.crane and not header.crane_assignment:
            continue
        expense = frappe.get_doc("Expense Entry", header.name)
        if not expense.journal_entry or not frappe.db.exists("Journal Entry", expense.journal_entry):
            unposted_expenses.append(expense.name)
            continue
        journal = frappe.get_doc("Journal Entry", expense.journal_entry)
        journal.check_permission("read")
        if journal.docstatus != 1 or journal.company != expense.company:
            unposted_expenses.append(expense.name)
            continue
        accounts = ", ".join(sorted({row.account for row in journal.accounts if row.credit}))
        data.append(dict(posting_date=expense.posting_date, voucher_type="Expense Entry",
                         voucher=expense.name, assignment=expense.crane_assignment,
                         crane=expense.crane, description=expense.description,
                         mode_of_payment=expense.mode_of_payment, source_account=accounts,
                         expenses=sum(flt(row.amount) for row in expense.expenses), currency=currency))
    data.sort(key=lambda row: (getdate(row["posting_date"]), row["voucher_type"], row["voucher"]))
    for row in data:
        row["income"] = flt(row.get("income"))
        row["expenses"] = flt(row.get("expenses"))
        row["net_sales"] = row["income"] - row["expenses"]
    income = sum(row["income"] for row in data)
    expenses = sum(row["expenses"] for row in data)
    summary = [dict(label=_(label), value=value, datatype="Currency", currency=currency,
                    indicator=indicator) for label, value, indicator in (
                        ("Total Income", income, "Green"), ("Total Expenses", expenses, "Red"),
                        ("Net Sales (Income - Expenses)", income - expenses,
                         "Green" if income >= expenses else "Red"))]
    message = _("Submitted documents only, by posting date, in company currency. Invoice amounts exclude taxes. "
                "Net Sales means rental income minus recorded costs, not cash collected. "
                "Treasury transfers and invoice payments are excluded to avoid counting costs twice. "
                "Assignment filters require expenses to have an Assignment link; crane filters require a Crane link.")
    if unposted_expenses:
        message += "<br><strong>" + _("Expenses excluded from totals because they have no valid submitted Journal Entry: {0}. "
                                    "Review these historical records before relying on the totals.").format(
                                        escape_html(", ".join(sorted(unposted_expenses)))) + "</strong>"
    return get_columns(), data, message, None, summary


def get_columns():
    return [
        dict(fieldname="posting_date", label=_("Posting Date"), fieldtype="Date", width=105),
        dict(fieldname="voucher_type", label=_("Document Type"), fieldtype="Data", width=125),
        dict(fieldname="voucher", label=_("Document"), fieldtype="Dynamic Link", options="voucher_type", width=175),
        dict(fieldname="assignment", label=_("Assignment"), fieldtype="Link", options="Crane Assignment", width=125),
        dict(fieldname="crane", label=_("Crane"), fieldtype="Link", options="Crane", width=125),
        dict(fieldname="description", label=_("Description"), fieldtype="Data", width=240),
        dict(fieldname="mode_of_payment", label=_("Mode of Payment"), fieldtype="Link", options="Mode of Payment", width=150),
        dict(fieldname="source_account", label=_("Source Account"), fieldtype="Data", width=200),
        *[dict(fieldname=field, label=_(label), fieldtype="Currency", options="currency", width=145)
          for field, label in (("income", "Income"), ("expenses", "Expenses"), ("net_sales", "Net Sales"))],
        dict(fieldname="currency", label=_("Currency"), fieldtype="Link", options="Currency", hidden=1),
    ]
