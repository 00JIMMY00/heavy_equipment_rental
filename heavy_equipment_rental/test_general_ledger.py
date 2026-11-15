"""Regression checks for native GL rental scoping (no ledger writes)."""
import unittest
from unittest.mock import patch

import frappe
from erpnext.accounts.report.general_ledger import general_ledger as native
from heavy_equipment_rental import general_ledger as rental


class TestRentalGeneralLedger(unittest.TestCase):
    def test_snapshot_maps_expense_to_native_journal(self):
        doc = frappe._dict(journal_entry="SETTLEMENT", source_snapshot=frappe.as_json([
            dict(doctype="Expense Entry", name="EXPENSE", journal="EXPENSE-JV"),
            dict(doctype="Sales Invoice", name="INVOICE"),
            dict(doctype="Sales Invoice", name="INVOICE"),
        ]))
        self.assertEqual(rental.settlement_vouchers(doc), {
            ("Journal Entry", "SETTLEMENT"), ("Journal Entry", "EXPENSE-JV"),
            ("Sales Invoice", "INVOICE"),
        })

    def test_mismatched_company_or_crane_rejected(self):
        doc = frappe._dict(company="Company A", crane="Crane A")
        doc.check_permission = lambda *args: None
        with patch.object(frappe, "get_doc", return_value=doc):
            for company, crane in [("Company B", "Crane A"), ("Company A", "Crane B")]:
                with self.assertRaises(frappe.ValidationError):
                    rental.voucher_scope(frappe._dict(cps="CPS", company=company, crane=crane))

    def test_empty_scope_and_native_isolation(self):
        company = frappe.db.get_value("Company", {}, "name")
        if not company:
            self.skipTest("Requires a development company")
        filters = dict(company=company, from_date="2026-01-01", to_date="2026-12-31")
        before = native.execute(frappe._dict(filters))
        conditions = native.get_conditions
        with patch.object(rental, "voucher_scope", return_value=set()):
            result = rental.execute(frappe._dict(filters))
        self.assertFalse(any(row.get("voucher_no") for row in result[1]))
        self.assertIs(native.get_conditions, conditions)
        self.assertEqual(before, native.execute(frappe._dict(filters)))

    def test_filter_script_and_controller(self):
        script = rental.get_script("General Ledger")["script"]
        self.assertIn('fieldname: "cps"', script)
        self.assertIn('fieldname: "crane"', script)
        self.assertIsInstance(frappe.get_doc("Report", "General Ledger"), rental.RentalReport)
