from collections import Counter, defaultdict
from decimal import Decimal

from frappe import _

from heavy_equipment_rental.partner_reporting import execute_report


STATEMENT_COLUMNS = (
    "partner_name", "posting_date", "movement_type", "outstanding_amount", "paid_amount",
    "entitlement", "pending_entitlement", "status", "voucher_no", "settlement", "timesheet",
    "crane", "sales_invoice", "invoice_value", "invoice_grand_total", "operating_amount",
    "residual_amount", "currency", "voucher_type",
)
TOTALS = (
    ("outstanding_amount", "Outstanding", "Orange"),
    ("paid_amount", "Paid / Adjusted", "Green"),
    ("entitlement", "Posted Entitlement", "Blue"),
    ("pending_entitlement", "Pending Entitlement", "Gray"),
)
AGE_BANDS = ("0-30 Days", "31-60 Days", "61-90 Days", "91+ Days")


def execute(filters=None):
    columns, rows, _message = execute_report(filters, summary=False)
    definitions = {column["fieldname"]: column for column in columns}
    columns = [definitions[field] for field in STATEMENT_COLUMNS]
    definitions["partner_name"].update(sticky=True, width=240)
    definitions["voucher_type"]["hidden"] = 1  # The Dynamic Link still uses this field.
    for field, width in (
        ("posting_date", 125), ("movement_type", 175), ("outstanding_amount", 150),
        ("entitlement", 165), ("pending_entitlement", 175), ("status", 165),
    ):
        definitions[field]["width"] = width
    by_currency = defaultdict(list)
    for row in rows:
        by_currency[row["currency"]].append(row)

    summary = [
        dict(label=_(label), value=sum(Decimal(str(row.get(field) or 0)) for row in movements),
             currency=currency, datatype="Currency", indicator=color)
        for currency, movements in sorted(by_currency.items())
        for field, label, color in TOTALS
    ]
    multiple_currencies = len(by_currency) > 1
    chart = get_aging_chart(rows) if not multiple_currencies else None
    message = _("Payments and balances use the payment ledger as of Report Date. The charts show positive outstanding balances by days since settlement posting. Allocated Invoice Value is split across partners.")
    if multiple_currencies:
        message += " " + _("Select one currency to see charts and table totals.")
    return columns, rows, message, chart, summary or None, int(multiple_currencies)


def get_aging_chart(rows):
    totals = defaultdict(lambda: [Decimal(0) for _ in AGE_BANDS])
    names = {}
    for row in rows:
        if (row.get("outstanding_amount") or 0) <= 0:
            continue
        partner = row["shareholder"] or row["party"]
        names[partner] = row.get("partner_name") or partner
        for index in range(len(AGE_BANDS)):
            totals[partner][index] += Decimal(str(row.get(f"range{index + 1}") or 0))
    if not totals:
        return None

    counts = Counter(names.values())
    ordered = sorted(totals, key=lambda partner: (-sum(totals[partner]), names[partner], partner))
    top = ordered[:5]
    names_to_show = [f"{names[key]} ({key})" if counts[names[key]] > 1 else names[key] for key in top]
    amounts = [totals[key] for key in top]
    if len(ordered) > len(top):
        names_to_show.append(_("Other Partners"))
        amounts.append([sum(totals[key][i] for key in ordered[len(top):]) for i in range(len(AGE_BANDS))])

    bands = [_(label) for label in AGE_BANDS]
    colors = ["#18794E", "#3677A8", "#AF6C1E", "#BF4045"]
    aging_totals = [float(sum(values)) for values in zip(*amounts)]
    return dict(
        type="bar", title=_("Outstanding by Partner"), currency=rows[0]["currency"],
        colors=colors, showLegend=0, barOptions=dict(stacked=True),
        data=dict(labels=names_to_show, datasets=[
            dict(name=label, values=[float(row[i]) for row in amounts]) for i, label in enumerate(bands)
        ]),
        partner_aging=dict(type="donut", title=_("Outstanding by Age"), showLegend=0, colors=colors,
                           data=dict(labels=bands, datasets=[dict(values=aging_totals)])),
    )
