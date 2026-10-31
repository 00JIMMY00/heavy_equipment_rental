"""Integration checks for employee expense posting and historical repair."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from heavy_equipment_rental.patches.backfill_expense_employee_parties import backfill_expense


class TestExpenseParties(FrappeTestCase):
    def make_expense(self, with_employee=True):
        expense_type = frappe.get_all(
            "Expense Entry Type", filters={"enabled": 1}, fields=["name", "company"], limit=1,
        )[0]
        employee = frappe.db.get_value("Employee", {"company": expense_type.company}, "name")
        self.assertTrue(employee, "An employee is required for the expense integration tests")
        mode = frappe.db.get_value("Mode of Payment Account", {"company": expense_type.company}, "parent")
        expense = frappe.get_doc({
            "doctype": "Expense Entry", "company": expense_type.company,
            "posting_date": today(), "description": "Employee party integration test",
            "mode_of_payment": mode, "employee": employee if with_employee else None,
            "expenses": [
                {"expense_entry_type": expense_type.name, "amount": 125},
                {"expense_entry_type": expense_type.name, "amount": 75},
            ],
        }).insert()
        expense.submit()
        return expense

    def ledger(self, expense):
        return frappe.get_all("GL Entry", filters={
            "voucher_type": "Journal Entry", "voucher_no": expense.journal_entry, "is_cancelled": 0,
        }, fields=["name", "debit", "credit", "party_type", "party"])

    def assert_parties(self, expense):
        journal = frappe.get_doc("Journal Entry", expense.journal_entry)
        self.assertEqual(journal.docstatus, 1)
        self.assertEqual(journal.total_debit, 200)
        self.assertEqual(journal.total_credit, 200)
        for row in journal.accounts:
            if row.debit and expense.employee:
                self.assertEqual((row.party_type, row.party), ("Employee", expense.employee))
            else:
                self.assertFalse(row.party_type)
                self.assertFalse(row.party)
        for row in self.ledger(expense):
            self.assertFalse(row.party_type)
            self.assertFalse(row.party)

    def clear_parties(self, expense):
        journal = frappe.get_doc("Journal Entry", expense.journal_entry)
        for doctype, rows in (("Journal Entry Account", journal.accounts), ("GL Entry", self.ledger(expense))):
            for row in rows:
                frappe.db.set_value(doctype, row.name, {"party_type": None, "party": None})

    def test_employee_on_journal_with_native_ledger_and_cancellation(self):
        expense = self.make_expense()
        self.assert_parties(expense)
        # Reposting uses the persisted source link rather than submission flags.
        journal = frappe.get_doc("Journal Entry", expense.journal_entry)
        self.assertTrue(all(not row.party for row in journal.build_gl_map()))
        expense.cancel()
        self.assertEqual(frappe.db.get_value("Journal Entry", expense.journal_entry, "docstatus"), 2)
        self.assertFalse(self.ledger(expense))

    def test_expense_without_employee(self):
        self.assert_parties(self.make_expense(with_employee=False))

    def test_unrelated_journal_keeps_native_party_validation(self):
        expense = self.make_expense()
        journal = frappe.copy_doc(frappe.get_doc("Journal Entry", expense.journal_entry))
        journal.docstatus = 0
        journal.insert()
        self.assertTrue(any(row.party for row in journal.build_gl_map()))
        with self.assertRaises(frappe.ValidationError):
            journal.submit()

    def test_backfill_is_idempotent_and_preserves_amounts(self):
        expense = self.make_expense()
        self.clear_parties(expense)
        before = frappe.db.get_value("Journal Entry", expense.journal_entry, "modified")
        backfill_expense(expense.name)
        self.assert_parties(expense)
        backfill_expense(expense.name)
        self.assert_parties(expense)
        self.assertEqual(frappe.db.get_value("Journal Entry", expense.journal_entry, "modified"), before)

    def test_backfill_preserves_conflicting_party(self):
        expense = self.make_expense()
        self.clear_parties(expense)
        journal = frappe.get_doc("Journal Entry", expense.journal_entry)
        frappe.db.set_value("Journal Entry Account", journal.accounts[0].name, "party_type", "Supplier")
        backfill_expense(expense.name)
        journal.reload()
        self.assertEqual(journal.accounts[0].party_type, "Supplier")
        self.assertFalse(journal.accounts[1].party)
        self.assertTrue(all(not row.party for row in self.ledger(expense)))
