from frappe import _

from heavy_equipment_rental.partner_reporting import execute_report


def execute(filters=None):
    columns, rows, _message = execute_report(filters, summary=True)
    if not any(row["pending_entitlement"] for row in rows):
        columns = [column for column in columns if column["fieldname"] != "pending_entitlement"]

    multiple_currencies = len({row["currency"] for row in rows}) > 1
    if multiple_currencies:
        currency = columns.pop()
        currency.update(hidden=0, width=95)
        columns.insert(1, currency)

    rows.sort(key=lambda row: (-row["outstanding_amount"], row["partner_name"] or row["party"], row["currency"]))
    message = _("Click an outstanding amount to open that partner’s statement.")
    if multiple_currencies:
        message += " " + _("Table totals are available when all rows use the same currency.")
    return columns, rows, message, None, None, int(multiple_currencies)
