"""Open Sales Invoices using ERPNext's as-of Payment Ledger balances."""

from collections import Counter, defaultdict

import frappe
from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute as receivables
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

GROUP_FIELDS = {"Customer": "customer", "Customer Group": "customer_group", "Territory": "territory"}
AMOUNTS = ("invoiced", "paid", "credit_note", "outstanding", "overdue")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    for doctype in ("Company", "Customer", "Sales Invoice", "GL Entry"):
        frappe.has_permission(doctype, "read", throw=True)
    company = get_company(filters.company)
    report_date = getdate(filters.report_date or nowdate())
    group_by = filters.group_by or "Customer"
    if group_by not in (*GROUP_FIELDS, "Invoice"):
        frappe.throw(_("Invalid Group By option"))

    due_status = filters.due_status or ("Overdue" if cint(filters.overdue_only) else "")
    if due_status not in ("", "All", "Overdue", "Not Due"):
        frappe.throw(_("Invalid Due Status option"))
    rows = get_invoice_rows(company, report_date, filters.customer, due_status)
    return (
        get_columns(),
        group_rows(rows, group_by),
        _("Open sales invoices as of the selected date, in company currency. Paid amounts follow ERPNext allocations. "
          "Credit notes are shown separately. Collection opens an unsaved Payment Entry using the current balance."),
        get_chart(rows),
        get_summary(rows, company.default_currency),
        1,
    )


def get_company(name):
    if name:
        company = frappe.get_doc("Company", name)
        company.check_permission("read")
        return company
    companies = frappe.get_list("Company", fields=["name", "default_currency"], order_by="name", limit_page_length=0)
    default = frappe.defaults.get_user_default("Company")
    company = next((row for row in companies if row.name == default), companies[0] if companies else None)
    if not company:
        frappe.throw(_("Not permitted for this company"), frappe.PermissionError)
    return company


def get_invoice_rows(company, report_date, customer_name=None, due_status=None):
    invoice_filters = {"company": company.name, "docstatus": 1, "is_return": 0, "posting_date": ["<=", report_date]}
    if customer_name:
        invoice_filters["customer"] = customer_name
    invoices = {row.name: row for row in frappe.get_list(
        "Sales Invoice", filters=invoice_filters,
        fields=["name", "customer", "posting_date", "due_date"], limit_page_length=0,
    )}
    if not invoices:
        return []
    customers = {row.name: row for row in frappe.get_list(
        "Customer", filters={"name": ["in", sorted({doc.customer for doc in invoices.values()})]},
        fields=["name", "customer_name", "customer_group", "territory"], limit_page_length=0,
    )}
    if not customers:
        return []

    native_rows = receivables(dict(
        company=company.name, report_date=report_date, party_type="Customer", party=list(customers),
        ageing_based_on="Due Date", age_as_on="Report Date", ignore_accounts=1,
    ))[1]
    precision = frappe.get_precision("Sales Invoice", "base_grand_total", currency=company.default_currency)
    rows = []
    for native in native_rows:
        invoice = invoices.get(native.get("voucher_no"))
        if native.get("voucher_type") != "Sales Invoice" or not invoice or invoice.customer not in customers:
            continue
        outstanding = flt(native.get("outstanding"), precision)
        days = max(0, date_diff(report_date, invoice.due_date or invoice.posting_date))
        if outstanding <= 0 or (due_status == "Overdue" and not days) or (due_status == "Not Due" and days):
            continue
        customer = customers[invoice.customer]
        rows.append(frappe._dict(
            label=customer.customer_name or customer.name, customer=customer.name,
            customer_group=customer.customer_group, territory=customer.territory,
            invoice=invoice.name, posting_date=invoice.posting_date, due_date=invoice.due_date,
            days_overdue=days, status=_("Overdue") if days else _("Not Due"),
            invoiced=flt(native.get("invoiced"), precision), paid=flt(native.get("paid"), precision),
            credit_note=flt(native.get("credit_note"), precision), outstanding=outstanding,
            overdue=outstanding if days else 0, currency=company.default_currency, indent=0,
        ))
    return sorted(rows, key=lambda row: (-row.days_overdue, row.due_date or row.posting_date, row.invoice))


def get_columns():
    return [dict(fieldname=field, label=_(label), fieldtype=fieldtype, options=options, width=width,
                 sticky=field == "label")
            for field, label, fieldtype, options, width in (
                ("label", "Customer / Group", "Data", None, 205),
                ("invoice", "Sales Invoice", "Link", "Sales Invoice", 160),
                ("outstanding", "Outstanding", "Currency", "currency", 165),
                ("overdue", "Overdue Amount", "Currency", "currency", 145),
                ("paid", "Total Paid", "Currency", "currency", 130),
                ("payment", "Payment", "Data", None, 175),
                ("invoiced", "Invoice Total", "Currency", "currency", 135),
                ("credit_note", "Credit Note", "Currency", "currency", 120),
                ("due_date", "Due Date", "Date", None, 105),
                ("days_overdue", "Days Overdue", "Int", None, 115),
                ("status", "Status", "Data", None, 100),
                ("posting_date", "Posting Date", "Date", None, 105),
            )]


def group_rows(rows, group_by):
    if group_by == "Invoice":
        return rows
    groups = defaultdict(list)
    for row in rows:
        groups[row[GROUP_FIELDS[group_by]]].append(row)
    data = []
    for key, children in sorted(groups.items(), key=lambda item: -sum(row.outstanding for row in item[1])):
        first = children[0]
        parent = frappe._dict(
            label=first.label if group_by == "Customer" else key or _("Not Set"),
            customer=first.customer if group_by == "Customer" else None,
            currency=first.currency, indent=0, is_group=1, invoice_names=[row.invoice for row in children],
        )
        parent.update({amount: sum(row[amount] for row in children) for amount in AMOUNTS})
        data.append(parent)
        data.extend(frappe._dict(row, indent=1) for row in children)
    return data


def get_chart(rows):
    if not rows:
        return None
    totals = defaultdict(lambda: [0, 0])
    names = {}
    for row in rows:
        totals[row.customer][bool(row.days_overdue)] += row.outstanding
        names[row.customer] = row.label
    name_counts = Counter(names.values())
    customers = sorted(totals, key=lambda customer: (-sum(totals[customer]), names[customer], customer))
    top = customers[:5]
    labels = [f"{names[customer]} ({customer})" if name_counts[names[customer]] > 1 else names[customer]
              for customer in top]
    if len(customers) > len(top):
        labels.append(_("Other Customers"))
    balances = [totals[customer] for customer in top]
    if len(customers) > len(top):
        balances.append([sum(totals[customer][i] for customer in customers[len(top):]) for i in (0, 1)])
    breakdown = [sum(balance[i] for balance in balances) for i in (0, 1)]
    currency = rows[0].currency
    precision = frappe.get_precision("Sales Invoice", "base_grand_total", currency=currency)
    statuses = [_("Not Due"), _("Overdue")]
    colors = ["#18794E", "#BF4045"]
    return dict(
        type="bar", title=_("Outstanding by Customer"), currency=currency, precision=precision,
        colors=colors, showLegend=0, barOptions=dict(stacked=True),
        data=dict(labels=labels, datasets=[
            dict(name=status, values=[balance[i] for balance in balances]) for i, status in enumerate(statuses)
        ]),
        receivable_breakdown=dict(type="donut", title=_("Outstanding by Due Status"), showLegend=0, colors=colors,
                                  data=dict(labels=statuses, datasets=[dict(values=breakdown)])),
    )


def get_summary(rows, currency):
    summary = [dict(label=_(label), value=sum(row[field] for row in rows), datatype="Currency",
                    currency=currency, indicator=indicator)
               for label, field, indicator in (
                   ("Invoice Total", "invoiced", "Blue"), ("Total Paid", "paid", "Green"),
                   ("Outstanding Amount", "outstanding", "Orange"), ("Overdue Amount", "overdue", "Red"),
               )]
    summary.insert(3, dict(label=_("Not Due Amount"), value=sum(row.outstanding - row.overdue for row in rows),
                           datatype="Currency", currency=currency, indicator="Green"))
    summary.append(dict(label=_("Open Invoices"), value=len(rows), datatype="Int", indicator="Blue"))
    return summary
