"""Carry the expense's driver into its accounting entries."""

import frappe
from frappe import _
from frappe.utils import flt

from arab_erp_theme.arab_erp_theme.doctype.expense_entry.expense_entry import ExpenseEntry
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry


class RentalExpenseEntry(ExpenseEntry):
    def on_submit(self):
        if not self.employee:
            return super().on_submit()
        # Keep the shared expense validation/cancellation behavior. Party belongs
        # on the expense lines; the cash/bank line has no employee balance.
        if self.journal_entry:
            frappe.throw(_("This Expense Entry already has a Journal Entry."))
        payment_account = self.get_accounting_details()
        self.validate_cost_center()
        accounts = []
        for row in self.expenses:
            account = {
                "account": row.expense_entry_account,
                "debit_in_account_currency": row.amount,
                "cost_center": self.cost_center,
            }
            account.update(party_type="Employee", party=self.employee)
            accounts.append(account)
        accounts.append({
            "account": payment_account,
            "credit_in_account_currency": sum(flt(row.amount) for row in self.expenses),
        })
        journal = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": self.company,
            "posting_date": self.posting_date,
            "mode_of_payment": self.mode_of_payment,
            "user_remark": _("Expense Entry {0}: {1}").format(self.name, self.description or ""),
            "accounts": accounts,
        })
        journal.flags.ignore_permissions = True
        journal.insert()
        # Persist the source before posting, so the GL mapper also works on
        # later reposts without relying on a request-local flag or remark text.
        self.db_set("journal_entry", journal.name, update_modified=False)
        journal.submit()


class RentalJournalEntry(JournalEntry):
    def build_gl_map(self):
        from heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction import (
            clear_treasury_gl_party,
        )

        gl_map = super().build_gl_map()
        clear_treasury_gl_party(self, gl_map)
        employee = frappe.db.get_value("Expense Entry", {
            "journal_entry": self.name, "docstatus": 1, "company": self.company,
        }, "employee")
        if employee:
            for row in gl_map:
                # Employee is attribution on an expense, not a receivable or
                # payable balance. Native GL validation forbids expense parties.
                if (
                    row.party_type == "Employee" and row.party == employee
                    and row.debit > 0 and not row.credit
                    and frappe.get_cached_value("Account", row.account, "root_type") == "Expense"
                ):
                    row.party_type = None
                    row.party = None
        return gl_map
