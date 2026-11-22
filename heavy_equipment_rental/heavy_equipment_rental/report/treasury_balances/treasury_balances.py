"""Current treasury balances and the last 30 days of posted GL movements."""

from datetime import timedelta
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import flt, formatdate, getdate, today

from heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction import (
    is_treasury_account,
)
from heavy_equipment_rental.heavy_equipment_rental.report.mode_of_payment_statement.mode_of_payment_statement import (
    payment_accounts,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company:
        frappe.throw(_("Select a Company."))
    company = frappe.get_doc("Company", filters.company)
    company.check_permission("read")
    for doctype in ("Account", "GL Entry", "Mode of Payment"):
        frappe.has_permission(doctype, "read", throw=True)

    last = getdate(today())
    days = [last - timedelta(days=offset) for offset in range(29, -1, -1)]
    currency = company.default_currency
    precision = frappe.get_precision("GL Entry", "debit", currency=currency)
    columns = [
        dict(fieldname="account", label=_("Account"), fieldtype="Link", options="Account", width=380),
        dict(fieldname="payment_modes", label=_("Mode of Payment"), fieldtype="Data", width=225),
        dict(fieldname="balance", label=_("Current Balance"), fieldtype="Currency", options="currency", width=175),
        dict(fieldname="currency", label=_("Currency"), fieldtype="Link", options="Currency", hidden=1),
    ]
    accounts = treasury_accounts(company.name)
    message = _("Balances as of {0} in {1}. Credit balances are negative.").format(formatdate(last), currency)
    if not accounts:
        return columns, [], message

    names = {account.name for account in accounts}
    modes = payment_accounts(frappe._dict(company=company.name), account_names=names)
    opening, daily = ledger_totals(company.name, sorted(names), days[0], last)
    total = [Decimal(0) for _ in days]
    rows, account_trends = [], []
    for account in accounts:
        running = opening.get(account.name, Decimal(0))
        trend = []
        for day in days:
            running += daily.get((account.name, day), Decimal(0))
            trend.append(running)
        if account.disabled and not any(trend):
            continue
        values = [flt(balance, precision) for balance in trend]
        rows.append(dict(account=account.name, payment_modes=" / ".join(modes.get(account.name, [])),
                         balance=values[-1], currency=currency))
        account_trends.append(dict(name=account.name, values=values))
        total = [combined + Decimal(str(balance)) for combined, balance in zip(total, values)]

    chart = dict(
        type="line", title=_("Daily Balance · Last 30 Days"), currency=currency, precision=precision,
        colors=["#2169BD"], showLegend=0, lineOptions=dict(hideDots=1, regionFill=1),
        data=dict(labels=[day.isoformat() for day in days], datasets=[
            dict(name=_("Total Balance"), values=[flt(balance, precision) for balance in total]),
        ]),
        treasury_accounts=account_trends,
    )
    summary = [
        dict(label=_("Total Balance"), value=flt(total[-1], precision), datatype="Currency", currency=currency,
             indicator="Red" if total[-1] < 0 else "Green"),
        dict(label=_("Treasury Accounts"), value=len(rows), datatype="Int", indicator="Blue"),
    ]
    return columns, rows, message, chart, summary


def treasury_accounts(company):
    accounts = frappe.get_list(
        "Account", filters={"company": company, "is_group": 0},
        or_filters=[["account_type", "in", ["Cash", "Bank"]],
                    ["her_treasury_kind", "in", ["Custody", "Employee Advance", "Owner Current"]]],
        fields=["name", "root_type", "account_type", "her_treasury_kind", "disabled"],
        order_by="account_name, name", limit_page_length=0,
    )
    return [account for account in accounts if is_treasury_account(account)]


def ledger_totals(company, accounts, first, last):
    filters = {"company": company, "account": ["in", accounts], "is_cancelled": 0}
    amounts = ["sum(debit) as total_debit", "sum(credit) as total_credit"]
    before = frappe.get_list(
        "GL Entry", filters=dict(filters, posting_date=["<", first]), fields=["account", *amounts],
        group_by="account", order_by="account", limit_page_length=0,
    )
    in_period = frappe.get_list(
        "GL Entry", filters=dict(filters, posting_date=["between", [first, last]]),
        fields=["account", "posting_date", *amounts], group_by="account, posting_date",
        order_by="account, posting_date", limit_page_length=0,
    )

    def net(row):
        return Decimal(str(row.total_debit or 0)) - Decimal(str(row.total_credit or 0))

    return ({row.account: net(row) for row in before},
            {(row.account, getdate(row.posting_date)): net(row) for row in in_period})
