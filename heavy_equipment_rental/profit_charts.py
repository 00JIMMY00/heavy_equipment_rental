"""Native Frappe report charts from the same filtered amounts as the table."""

from collections import defaultdict

from frappe import _
from frappe.utils import escape_html, flt


def comparison_chart(rows, group_label, series, currency, title, chronological=False):
    totals = defaultdict(lambda: [0.0] * len(series))
    for row in rows:
        values = totals[group_label(row)]
        for index, (field, _label, _color) in enumerate(series):
            values[index] += flt(row.get(field))
    if not totals:
        return None

    if chronological:
        labels = sorted(totals)[-12:]
        if len(totals) > len(labels):
            title = _("{0} (latest 12 months)").format(title)
    else:
        labels = sorted(totals, key=lambda label: (-max(map(abs, totals[label])), label))[:10]
        if len(totals) > len(labels):
            title = _("{0} (10 largest by amount)").format(title)
    datasets = [
        dict(name=_(label), values=[totals[key][index] for key in labels])
        for index, (_field, label, _color) in enumerate(series)
    ]
    return dict(
        type="bar", title=title, fieldtype="Currency", options=currency,
        disableEntryAnimation=True, colors=[color for _field, _label, color in series],
        data=dict(labels=[escape_html(label) for label in labels], datasets=datasets),
    )
