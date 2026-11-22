"""Posted rental income and costs, in company currency and excluding invoice taxes."""

from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.utils import escape_html, flt, getdate

from heavy_equipment_rental.profit_charts import comparison_chart


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not all(filters.get(key) for key in ("company", "from_date", "to_date")):
        frappe.throw(_("Company, From Date and To Date are required."))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date must be before To Date."))
    frappe.get_doc("Company", filters.company).check_permission("read")
    # Never return a plausible but incomplete profit because a source is inaccessible.
    for doctype in ("Rental Contract", "Crane", "Crane Timesheet", "Sales Invoice",
                    "Purchase Invoice", "Grouped Expense", "Journal Entry"):
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(_("Read permission for {0} is required for this report.").format(doctype),
                         frappe.PermissionError)
    currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    assignments = frappe.get_list("Rental Contract", filters={"company": filters.company},
                                  pluck="name", limit_page_length=0)
    if filters.assignment:
        assignments = [name for name in assignments if name == filters.assignment]
    cranes = frappe.get_list("Crane", fields=["name", "item", "crane_name"], limit_page_length=0)
    items = {row.name: row.item for row in cranes if not filters.crane or row.name == filters.crane}
    crane_names = {row.name: row.crane_name or row.name for row in cranes}
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
        }, or_filters=[["name", "in", list(links)], ["return_against", "in", list(links)]],
            fields=["name", "return_against", "posting_date"], limit_page_length=0)
        invoice_items = defaultdict(list)
        if invoices:
            for row in frappe.get_all(doctype + " Item", filters={"parent": ["in", [h.name for h in invoices]],
                        "parenttype": doctype}, fields=["parent", "item_code", "crane", "base_net_amount", "description"],
                        order_by="parent, idx"):
                invoice_items[row.parent].append(row)
        for header in invoices:
            mapping = links.get(header.name) or links.get(header.return_against)
            if not mapping:
                continue
            for line in invoice_items[header.name]:
                sources = mapping.get(line.item_code)
                if sources and line.get("crane"):
                    sources = {source for source in sources if source[1] == line.crane}
                if not sources:
                    continue
                if len(sources) != 1:
                    frappe.throw(_("Invoice {0} has ambiguous rental links; review its Timesheets.").format(header.name))
                assignment, crane = next(iter(sources))
                data.append(dict(posting_date=header.posting_date, voucher_type=doctype,
                                 voucher=header.name, assignment=assignment, crane=crane,
                                 description=line.description, currency=currency,
                                 **{amount_field: flt(line.base_net_amount)}))
    unposted_expenses = []
    # Native repair ledger costs and attributed depreciation/other journals.
    # These sources are independent of customer billing and cash disbursement.
    from heavy_equipment_rental.consolidated_accounting import fleet_sources
    from heavy_equipment_rental.crane_repairs import fleet_repair_expenses
    from heavy_equipment_rental.profit_sharing import attributed_journals

    period = [getdate(filters.from_date), getdate(filters.to_date)]
    for crane, journal, source in fleet_sources(items, filters.company, period, filters.assignment,
            include_legacy=True, unposted=unposted_expenses):
        if source["rental_assignment"] and source["rental_assignment"] not in assignments:
            continue
        data.append(dict(posting_date=source["posting_date"], voucher_type="Grouped Expense",
            source_account=", ".join(sorted({r.account for r in journal.accounts if r.credit})),
            voucher=source["consolidated_expense"], assignment=source["rental_assignment"], crane=crane,
            description=source["description"], mode_of_payment=source["mode_of_payment"],
            expenses=source["expenses"], currency=currency))
    for crane, source in fleet_repair_expenses(items, filters.company, period):
        assignment = source.get("rental_assignment")
        if (assignment and assignment not in assignments) or (filters.assignment and assignment != filters.assignment):
            continue
        data.append(dict(posting_date=source["posting_date"], voucher_type=source["doctype"],
            voucher=source["name"], assignment=assignment, crane=crane,
            description=_("Repair parts / external services"), expenses=source["expenses"], currency=currency))
    if not filters.assignment:
        for crane, source in attributed_journals(items, filters.company, *period):
            data.append(dict(posting_date=source["posting_date"], voucher_type=source["doctype"],
                voucher=source["name"], crane=crane, currency=currency,
                description=_("Depreciation") if source.get("is_depreciation") else _("Attributed journal"),
                income=source.get("revenue", 0), expenses=source.get("expenses", 0)))
    data.sort(key=lambda row: (getdate(row["posting_date"]), row["voucher_type"], row["voucher"]))
    for row in data:
        row["crane_name"] = crane_names[row["crane"]]
        row["income"] = flt(row.get("income"))
        row["expenses"] = flt(row.get("expenses"))
        row["net_sales"] = row["income"] - row["expenses"]
    income = sum(row["income"] for row in data)
    expenses = sum(row["expenses"] for row in data)
    summary = [dict(label=_(label), value=value, datatype="Currency", currency=currency,
                    indicator=indicator) for label, value, indicator in (
                        ("Total Income", income, "Green"), ("Total Expenses", expenses, "Red"),
                        ("Net Profit", income - expenses,
                         "Green" if income >= expenses else "Red"))]
    message = _("Amounts use posting dates and company currency. Income excludes invoice taxes. "
                "Costs include posted hire, linked expense payments, repairs and attributed journals. "
                "Driver salary enters costs when a linked payment posts.")
    if unposted_expenses:
        message += "<br><strong>" + _("Expenses excluded from totals because they have no valid submitted Journal Entry: {0}. "
                                    "Review these historical records before relying on the totals.").format(
                                        escape_html(", ".join(sorted(unposted_expenses)))) + "</strong>"
    view = filters.view or "Document Details"
    dimension = {"By Crane": "crane", "By Contract": "assignment", "By Month": "month",
                 "Document Details": "crane"}.get(view)
    if not dimension:
        frappe.throw(_("Invalid report view."))
    grouped = {}
    for row in data:
        key = str(row["posting_date"])[:7] if dimension == "month" else row.get(dimension)
        group = grouped.setdefault(key, {dimension: key, "currency": currency, "income": 0,
                                         "expenses": 0, "net_sales": 0})
        for field in ("income", "expenses", "net_sales"):
            group[field] += row[field]
    columns = get_columns()
    series = [("income", "Income", "#2563eb"), ("expenses", "Expenses", "#df626b"),
              ("net_sales", "Net Profit", "#0d9488")]
    titles = {"crane": _("Profit by crane"), "assignment": _("Profit by contract"), "month": _("Monthly profit")}
    if dimension == "crane":
        name_counts = Counter(crane_names[key] for key in grouped)
        for key, group in grouped.items():
            name = crane_names[key]
            group["crane_name"] = name
            group["chart_label"] = name if name_counts[name] == 1 else f"{name} ({key})"
    chart = comparison_chart(grouped.values(), lambda row: row.get("chart_label") or row[dimension] or _("Unassigned"),
                             series, currency, titles[dimension], chronological=dimension == "month")
    if view != "Document Details":
        display_field = "crane_name" if dimension == "crane" else dimension
        ordered = sorted(grouped.values(), key=lambda row: row[display_field] or "")
        key_column = (dict(fieldname="month", label=_("Month"), fieldtype="Data", width=140)
                      if dimension == "month" else next(col for col in columns if col["fieldname"] == display_field))
        fields = {"income", "expenses", "net_sales", "currency"}
        if dimension == "crane":
            fields.add("crane")  # Hidden Link keeps the document identity alongside its display name.
        columns = [dict(key_column, sticky=True)] + [col for col in columns if col["fieldname"] in fields]
        data = ordered
    return columns, data, message, chart, summary


def get_columns():
    return [
        dict(fieldname="posting_date", label=_("Posting Date"), fieldtype="Date", width=105),
        dict(fieldname="voucher_type", label=_("Document Type"), fieldtype="Data", width=125),
        dict(fieldname="voucher", label=_("Document"), fieldtype="Dynamic Link", options="voucher_type", width=175),
        dict(fieldname="assignment", label=_("Rental Contract"), fieldtype="Link", options="Rental Contract", width=125),
        dict(fieldname="crane_name", label=_("Crane Name"), fieldtype="Data", width=205),
        dict(fieldname="crane", label=_("Crane"), fieldtype="Link", options="Crane", hidden=1),
        dict(fieldname="description", label=_("Description"), fieldtype="Data", width=240),
        dict(fieldname="mode_of_payment", label=_("Mode of Payment"), fieldtype="Link", options="Mode of Payment", width=150),
        dict(fieldname="source_account", label=_("Source Account"), fieldtype="Data", width=200),
        *[dict(fieldname=field, label=_(label), fieldtype="Currency", options="currency", width=145)
          for field, label in (("income", "Income"), ("expenses", "Expenses"), ("net_sales", "Net Profit"))],
        dict(fieldname="currency", label=_("Currency"), fieldtype="Link", options="Currency", hidden=1),
    ]
