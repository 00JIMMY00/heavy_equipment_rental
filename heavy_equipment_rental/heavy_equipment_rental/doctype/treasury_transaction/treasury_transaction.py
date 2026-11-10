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
                ["company", "is_group", "disabled", "account_type", "account_currency",
                 "root_type", "her_treasury_kind"], as_dict=True,
            )
            if (
                not account or account.company != self.company or account.is_group or account.disabled
                or not is_treasury_account(account)
                or account.account_currency != self.currency
            ):
                frappe.throw(_("Select enabled company-currency Cash, Bank or explicitly designated custody/current accounts."))
        if self.source_account == self.destination_account:
            frappe.throw(_("Source and destination accounts must be different."))
        if self.cost_center:
            center = frappe.db.get_value("Cost Center", self.cost_center,
                ["company", "is_group", "disabled"], as_dict=True)
            if not center or center.company != self.company or center.is_group or center.disabled:
                frappe.throw(_("Select an enabled, non-group Cost Center for this Company."))
        if bool(self.party_type) != bool(self.party):
            frappe.throw(_("Select both Party Type and Party, or leave both empty."))
        if self.party_type and not frappe.db.exists("Party Type", self.party_type):
            frappe.throw(_("Select a registered Party Type."))

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
                {"account": self.source_account, "credit_in_account_currency": self.amount,
                 "cost_center": self.cost_center},
                {
                    "account": self.destination_account,
                    "debit_in_account_currency": self.amount,
                    "cost_center": self.cost_center,
                    "party_type": self.party_type,
                    "party": self.party,
                },
            ],
        })
        journal.insert()
        # Persist the source before GL mapping, including subsequent reposts.
        self.db_set("journal_entry", journal.name, update_modified=False)
        journal.submit()

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


def clear_treasury_gl_party(journal, gl_map):
    """Keep recipient attribution on the journal, not cash/bank GL balances."""
    transaction = frappe.db.get_value("Treasury Transaction", {
        "journal_entry": journal.name, "docstatus": 1, "company": journal.company,
        "party_type": ["is", "set"], "party": ["is", "set"],
    }, ["destination_account", "party_type", "party"], as_dict=True)
    if transaction:
        for row in gl_map:
            if (
                row.account == transaction.destination_account
                and row.party_type == transaction.party_type and row.party == transaction.party
                and row.debit > 0 and not row.credit
            ):
                row.party_type = None
                row.party = None


def is_treasury_account(account):
    if account.account_type in ("Cash", "Bank"):
        return account.root_type == "Asset"
    if account.account_type in ("Receivable", "Payable"):
        return False
    kind = account.get("her_treasury_kind")
    return ((kind in ("Custody", "Employee Advance") and account.root_type == "Asset")
            or (kind == "Owner Current" and account.root_type == "Liability"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def treasury_account_query(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe._dict(filters or {})
    if not filters.company:
        return []
    return frappe.get_list("Account", filters={
        "company": filters.company, "is_group": 0, "disabled": 0,
        "account_currency": frappe.get_cached_value("Company", filters.company, "default_currency"),
        "name": ["like", "%" + txt + "%"],
        "account_type": ["not in", ["Receivable", "Payable"]],
    }, or_filters={"account_type": ["in", ["Cash", "Bank"]],
                   "her_treasury_kind": ["in", ["Custody", "Employee Advance", "Owner Current"]]},
        fields=["name", "account_name"], as_list=True, start=start, page_length=page_len)
