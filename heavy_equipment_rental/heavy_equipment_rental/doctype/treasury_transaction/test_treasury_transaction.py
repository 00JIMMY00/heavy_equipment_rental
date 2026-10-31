"""Integration coverage for treasury posting, reversal, validation and permissions."""

from unittest.mock import patch

import erpnext
import frappe
import frappe.permissions
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today


class TestTreasuryTransaction(FrappeTestCase):
    def setUp(self):
        self.company = erpnext.get_default_company()
        self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        self.key = frappe.generate_hash(length=8)
        parent = frappe.db.get_value("Account", {
            "company": self.company, "account_type": "Cash", "is_group": 0,
        }, "parent_account")
        self.assertTrue(parent, "Development tests need a Company with a Cash account")
        self.accounts = []
        for account_type in ("Cash", "Bank"):
            self.accounts.append(frappe.get_doc({
                "doctype": "Account", "company": self.company,
                "account_name": "Treasury test " + account_type + self.key,
                "parent_account": parent, "account_type": account_type,
                "account_currency": self.currency,
            }).insert().name)
        self.mode = frappe.get_doc({
            "doctype": "Mode of Payment", "mode_of_payment": "Treasury test " + self.key,
            "type": "Cash", "enabled": 1,
            "accounts": [{"company": self.company, "default_account": self.accounts[0]}],
        }).insert()

    def transaction(self, **values):
        fields = {
            "doctype": "Treasury Transaction", "company": self.company,
            "posting_date": today(), "mode_of_payment": self.mode.name,
            "destination_account": self.accounts[1], "amount": 125.75,
            "description": "Treasury integration test",
        }
        fields.update(values)
        return frappe.get_doc(fields)

    def ledger(self, journal):
        return frappe.get_all("GL Entry", filters={
            "voucher_type": "Journal Entry", "voucher_no": journal, "is_cancelled": 0,
        }, fields=["account", "debit", "credit"])

    def test_post_reverse_and_amend(self):
        transfer = self.transaction().insert()
        self.assertFalse(transfer.journal_entry)
        self.assertEqual(transfer.source_account, self.accounts[0])
        transfer.submit()
        journal = frappe.get_doc("Journal Entry", transfer.journal_entry)
        self.assertEqual(journal.docstatus, 1)
        self.assertEqual(journal.company, self.company)
        self.assertEqual(getdate(journal.posting_date), getdate(transfer.posting_date))
        self.assertEqual(journal.total_debit, 125.75)
        self.assertEqual(journal.total_credit, 125.75)
        rows = {row.account: row for row in self.ledger(journal.name)}
        self.assertEqual(rows[self.accounts[0]].credit, 125.75)
        self.assertEqual(rows[self.accounts[1]].debit, 125.75)
        with self.assertRaises(frappe.ValidationError):
            transfer.on_submit()
        self.assertEqual(frappe.db.count("Journal Entry", {"user_remark": journal.user_remark}), 1)
        with self.assertRaises(frappe.ValidationError):
            journal.cancel()
        self.assertEqual(frappe.db.get_value("Journal Entry", journal.name, "docstatus"), 1)
        transfer.reload()
        transfer.cancel()
        self.assertEqual(frappe.db.get_value("Journal Entry", journal.name, "docstatus"), 2)
        self.assertFalse(self.ledger(journal.name))
        amendment = frappe.copy_doc(transfer, ignore_no_copy=False)
        amendment.docstatus = 0
        amendment.amended_from = transfer.name
        amendment.amount = 75
        amendment.insert()
        amendment.submit()
        self.assertNotEqual(amendment.journal_entry, journal.name)
        self.assertEqual(frappe.db.get_value("Journal Entry", amendment.journal_entry, "total_debit"), 75)

    def test_bank_to_cash(self):
        self.mode.accounts[0].default_account = self.accounts[1]
        self.mode.type = "Bank"
        self.mode.save()
        transfer = self.transaction(destination_account=self.accounts[0], reference_no="TR-123", reference_date=today()).insert()
        transfer.submit()
        journal = frappe.get_doc("Journal Entry", transfer.journal_entry)
        rows = {row.account: row for row in self.ledger(journal.name)}
        self.assertEqual(rows[self.accounts[1]].credit, transfer.amount)
        self.assertEqual(rows[self.accounts[0]].debit, transfer.amount)
        self.assertEqual(journal.cheque_no, "TR-123")

    def test_reject_invalid_amount_accounts_and_manual_journal(self):
        for values in ({"amount": 0}, {"amount": -1}, {"amount": 0.000001},
                       {"destination_account": self.accounts[0]},
                       {"journal_entry": "not-a-journal"}):
            with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
                self.transaction(**values).insert()
        for field, value in (("disabled", 1), ("account_type", "Receivable"),
                             ("company", "Wrong Company"), ("account_currency", "Wrong Currency"),
                             ("is_group", 1)):
            original = frappe.db.get_value("Account", self.accounts[1], field)
            try:
                frappe.db.set_value("Account", self.accounts[1], field, value)
                with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
                    self.transaction().insert()
            finally:
                frappe.db.set_value("Account", self.accounts[1], field, original)

    def test_payment_mode_requires_enabled_company_cash_or_bank_account(self):
        self.mode.enabled = 0
        self.mode.save()
        with self.assertRaises(frappe.ValidationError):
            self.transaction().insert()
        self.mode.enabled = 1
        self.mode.set("accounts", [])
        self.mode.save()
        with self.assertRaises(frappe.ValidationError):
            self.transaction().insert()
        self.mode.append("accounts", {"company": self.company, "default_account": self.accounts[0]})
        self.mode.save()
        frappe.db.set_value("Account", self.accounts[0], "account_type", "Receivable")
        with self.assertRaises(frappe.ValidationError):
            self.transaction().insert()

    def test_journal_permission_failure_rolls_back_submission(self):
        native_permission = frappe.permissions.has_permission
        for denied_permission in ("create", "submit"):
            transfer = self.transaction().insert()
            frappe.db.savepoint("treasury_permission")

            def permission(doctype, ptype="read", *args, **kwargs):
                if doctype == "Journal Entry" and ptype == denied_permission:
                    return False
                return native_permission(doctype, ptype, *args, **kwargs)

            try:
                with patch("frappe.permissions.has_permission", side_effect=permission):
                    with self.subTest(permission=denied_permission), self.assertRaises(frappe.PermissionError):
                        transfer.submit()
            finally:
                # Mirror Frappe's request rollback after a failed submission.
                frappe.db.rollback(save_point="treasury_permission")
            transfer.reload()
            self.assertEqual(transfer.docstatus, 0)
            self.assertFalse(transfer.journal_entry)
            self.assertFalse(frappe.db.exists("Journal Entry", {
                "user_remark": "Treasury Transaction {0}: Treasury integration test".format(transfer.name),
            }))
