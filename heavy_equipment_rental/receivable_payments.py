"""Prepare an unsaved native customer receipt for selected Sales Invoices."""

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe import _
from frappe.utils import flt, getdate

MAX_INVOICES = 200


@frappe.whitelist()
def make_payment_entry(invoices):
    frappe.has_permission("Payment Entry", "create", throw=True)
    if isinstance(invoices, str):
        invoices = frappe.parse_json(invoices)
    if not isinstance(invoices, list) or not 1 <= len(invoices) <= MAX_INVOICES:
        frappe.throw(_("Select between 1 and 200 invoices for one customer."))
    if any(not isinstance(name, str) or not name for name in invoices):
        frappe.throw(_("Invalid invoice selection"))

    documents = []
    today = getdate()
    unavailable = _("An invoice is no longer payable. Refresh the report and select open invoices.")
    for name in dict.fromkeys(invoices):
        invoice = frappe.get_doc("Sales Invoice", name)
        invoice.check_permission("read")
        if invoice.docstatus != 1 or invoice.is_return or flt(invoice.outstanding_amount) <= 0:
            frappe.throw(unavailable)
        if getdate(invoice.posting_date) > today:
            frappe.throw(_("Future-dated invoices cannot be paid from this report."))
        documents.append(invoice)

    first = documents[0]
    frappe.get_doc("Company", first.company).check_permission("read")
    frappe.get_doc("Customer", first.customer).check_permission("read")
    fields = ("customer", "company", "debit_to", "party_account_currency")
    account_details = tuple(first.get(field) for field in fields)
    if any(tuple(invoice.get(field) for field in fields) != account_details for invoice in documents[1:]):
        frappe.throw(_("Select invoices for the same customer, company, receivable account and currency."))

    payment = None
    for invoice in documents:
        mapped = get_payment_entry("Sales Invoice", invoice.name, bank_account=payment.paid_to if payment else None)
        if not mapped.references or sum(flt(row.allocated_amount) for row in mapped.references) <= 0:
            frappe.throw(unavailable)
        if payment is None:
            payment = mapped
            continue
        if (mapped.paid_from, mapped.paid_to) != (payment.paid_from, payment.paid_to):
            frappe.throw(_("These invoices require separate payments because their payment accounts differ."))
        for field in ("references", "deductions"):
            for row in mapped.get(field):
                values = row.as_dict(no_nulls=True)
                for key in ("name", "parent", "parenttype", "parentfield", "idx"):
                    values.pop(key, None)
                payment.append(field, values)
        payment.paid_amount += mapped.paid_amount
        payment.received_amount += mapped.received_amount
    if len(documents) > 1 and payment.paid_from and payment.paid_to:
        payment.set_amounts()
    return payment
