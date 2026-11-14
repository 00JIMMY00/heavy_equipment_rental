"""Allocate the native payment form's amount changes to a partner settlement."""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class PartnerPaymentEntry(PaymentEntry):
    @frappe.whitelist()
    def allocate_amount_to_references(self, paid_amount, paid_amount_change, allocate_payment_amount):
        # ERPNext v15's positive-payable allocator only handles Supplier/Employee.
        # Keep every other payment/reference workflow on the native implementation.
        if not (
            self.payment_type == "Pay"
            and self.party_type == "Shareholder"
            and self.references
            and all(r.reference_doctype == "Journal Entry" and not r.payment_request
                and flt(r.outstanding_amount) >= 0 for r in self.references)
            and self._only_settlement_references()
            and allocate_payment_amount
        ):
            return super().allocate_amount_to_references(
                paid_amount, paid_amount_change, allocate_payment_amount
            )

        precision = self.precision("paid_amount")
        available = flt(paid_amount) - sum(flt(row.amount, precision) for row in self.deductions)
        outstanding = {}
        for row in self.references:
            balance = outstanding.setdefault(row.reference_name, flt(row.outstanding_amount))
            row.allocated_amount = flt(min(max(available, 0), balance), precision)
            available = flt(available - row.allocated_amount, precision)
            outstanding[row.reference_name] = flt(balance - row.allocated_amount, precision)

    def _only_settlement_references(self):
        names = {r.reference_name for r in self.references}
        journals = frappe.get_all("Crane Profit Settlement", filters={
            "journal_entry": ["in", list(names)], "docstatus": 1, "company": self.company,
        }, pluck="journal_entry")
        return names == set(journals)



@frappe.whitelist()
def get_open_partner_entitlements(company, party_type, party, paid_to,
        from_date=None, to_date=None, crane=None, timesheet=None, sales_invoice=None):
    """Current ledger balances, restricted to this payment's party/company/payable account."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

    frappe.has_permission("Payment Entry", "read", throw=True)
    if not (frappe.has_permission("Payment Entry", "create") or frappe.has_permission("Payment Entry", "write")):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if party_type not in ("Shareholder", "Supplier"):
        frappe.throw(_("Select a partner (Shareholder or Supplier)."))
    for doctype, name in (("Company", company), (party_type, party), ("Account", paid_to)):
        frappe.get_doc(doctype, name).check_permission("read")
    account = frappe.get_cached_doc("Account", paid_to)
    if account.company != company or account.is_group or account.account_type != "Payable":
        frappe.throw(_("Select a payable account in the payment company."))
    if from_date and to_date and getdate(from_date) > getdate(to_date):
        frappe.throw(_("From Date must be before To Date."))
    journals = frappe.get_all("Journal Entry Account", filters={"parenttype": "Journal Entry",
        "docstatus": 1, "party_type": party_type, "party": party, "account": paid_to}, pluck="parent")
    if not journals:
        return []
    filters = {"company": company, "docstatus": 1, "journal_entry": ["in", journals]}
    for field, value in (("crane", crane), ("timesheet", timesheet), ("sales_invoice", sales_invoice)):
        if value:
            filters[field] = value
    if from_date and to_date:
        filters["posting_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["posting_date"] = [">=", from_date]
    elif to_date:
        filters["posting_date"] = ["<=", to_date]
    rows = frappe.get_list("Crane Profit Settlement", filters=filters,
        fields=["name", "posting_date", "crane", "timesheet", "sales_invoice", "journal_entry"],
        order_by="posting_date, name", limit_page_length=0)
    result = []
    for row in rows:
        for doctype, name in (("Crane Profit Settlement", row.name), ("Crane", row.crane),
                ("Crane Timesheet", row.timesheet), ("Sales Invoice", row.sales_invoice)):
            if name:
                frappe.get_doc(doctype, name).check_permission("read")
        details = get_reference_details("Journal Entry", row.journal_entry,
            account.account_currency, party_type, party)
        if flt(details.outstanding_amount) <= 0:
            continue
        result.append(dict(settlement=row.name, posting_date=row.posting_date, crane=row.crane,
            timesheet=row.timesheet, sales_invoice=row.sales_invoice, reference_doctype="Journal Entry",
            reference_name=row.journal_entry, total_amount=details.total_amount,
            outstanding_amount=details.outstanding_amount, exchange_rate=details.exchange_rate or 1,
            currency=account.account_currency))
    return result
