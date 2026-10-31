"""Fill missing Journal Entry attribution without changing the ledger."""

import frappe
from frappe.utils import flt


def execute():
    for name in frappe.get_all("Expense Entry", filters={
        "docstatus": 1, "employee": ["is", "set"], "journal_entry": ["is", "set"],
    }, pluck="name"):
        backfill_expense(name)


def backfill_expense(name):
    expense = frappe.get_doc("Expense Entry", name)
    if expense.docstatus != 1 or not expense.employee or not expense.journal_entry:
        return
    if not frappe.db.exists("Employee", expense.employee):
        return
    journal = frappe.get_doc("Journal Entry", expense.journal_entry, for_update=True)
    if journal.docstatus != 1 or journal.company != expense.company:
        return
    debits = [row for row in journal.accounts if row.debit > 0 and not row.credit]
    expected = [(row.expense_entry_account, flt(row.amount, row.precision("amount"))) for row in expense.expenses]
    actual = [(row.account, flt(row.debit_in_account_currency, row.precision("debit_in_account_currency"))) for row in debits]
    if sorted(expected) != sorted(actual):
        return
    # Skip ambiguous or manually changed postings, including partial parties.
    if any(
        (row.party_type or row.party)
        and (row.party_type != "Employee" or row.party != expense.employee)
        for row in debits
    ):
        return
    for row in debits:
        if not row.party_type and not row.party:
            frappe.db.set_value("Journal Entry Account", row.name, {
                "party_type": "Employee", "party": expense.employee,
            }, update_modified=False)
