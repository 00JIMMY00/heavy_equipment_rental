"""Transfer company funds from a payment mode to another cash/bank account."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class TreasuryTransaction(Document):
    def validate(self):
        if self.docstatus == 0 and self.journal_entry:
            frappe.throw(_("The Journal Entry is assigned automatically on submission."))
        self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        self.amount = flt(self.amount, self.precision("amount"))
        if self.amount <= 0:
            frappe.throw(_("Amount must be greater than zero."))
        if not frappe.db.get_value("Mode of Payment", self.mode_of_payment, "enabled"):
            frappe.throw(_("Select an enabled Mode of Payment."))
        self.source_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": self.mode_of_payment, "parenttype": "Mode of Payment", "company": self.company},
            "default_account",
        )
        if not self.source_account:
            frappe.throw(_("Set a Default Account for this Company on the Mode of Payment."))
        for account_name in (self.source_account, self.destination_account):
            account = frappe.db.get_value(
                "Account", account_name,
                ["company", "is_group", "disabled", "account_type", "account_currency"], as_dict=True,
            )
            if (
                not account or account.company != self.company or account.is_group or account.disabled
                or account.account_type not in ("Cash", "Bank")
                or account.account_currency != self.currency
            ):
                frappe.throw(_("Select enabled, non-group Cash or Bank accounts in the Company currency."))
        if self.source_account == self.destination_account:
            frappe.throw(_("Source and destination accounts must be different."))

    def on_submit(self):
        if self.journal_entry:
            frappe.throw(_("This Treasury Transaction already has a Journal Entry."))
        journal = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": self.company,
            "posting_date": self.posting_date,
            "mode_of_payment": self.mode_of_payment,
            "cheque_no": self.reference_no,
            "cheque_date": self.reference_date,
            "user_remark": _("Treasury Transaction {0}: {1}").format(self.name, self.description or ""),
            "accounts": [
                {"account": self.source_account, "credit_in_account_currency": self.amount},
                {"account": self.destination_account, "debit_in_account_currency": self.amount},
            ],
        })
        journal.insert()
        journal.submit()
        self.db_set("journal_entry", journal.name, update_modified=False)

    def on_cancel(self):
        if not self.journal_entry:
            frappe.throw(_("The linked Journal Entry is missing."))
        journal = frappe.get_doc("Journal Entry", self.journal_entry, for_update=True)
        if journal.docstatus != 1:
            frappe.throw(_("The linked Journal Entry must be submitted."))
        journal.ignore_linked_doctypes = ("Treasury Transaction",)
        journal.cancel()


def guard_journal_cancel(doc, method=None):
    transaction = frappe.db.get_value(
        "Treasury Transaction", {"journal_entry": doc.name, "docstatus": 1}, "name",
    )
    if transaction:
        frappe.throw(_("Cancel Treasury Transaction {0} to reverse this Journal Entry.").format(transaction))
