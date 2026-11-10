"""Workbook import / ledger reconciliation and report integration coverage."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import frappe
import openpyxl
from frappe.tests.utils import FrappeTestCase

from heavy_equipment_rental.treasury_workbook import HEADERS, import_libya_workbook, inspect_workbook, resolved_workbook
from heavy_equipment_rental.heavy_equipment_rental.report.treasury_workbook.treasury_workbook import download_workbook, execute, get_defaults


class TestTreasuryWorkbook(FrappeTestCase):
    def setUp(self):
        self.key = frappe.generate_hash(length=7)
        self.company = "_Test Treasury Libya " + self.key
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "treasury.xlsx"
        book = openpyxl.Workbook()
        sheet = book.active
        for index, header in enumerate(HEADERS, 1):
            sheet.cell(5, index, header)
        values = [
            [datetime(2026, 12, 10), 500, None, "الحاج / محمد خيري", "خزينه", "تغذية"],
            [datetime(2026, 12, 10), None, 100, "مرعي وائل", "نسريات", "مشتريات"],
            [None, None, 50, "رامي", "سلفة", "سلفة من الراتب"],
            ["13/10/2026", None, 30, "الحاج / محمد خيري", "شخصي محمد خيري", "شخصي"],
            [None, 40, None, "مصرف", "خزينه", "تغذية من المصرف"],
            [None, None, 20, "الحاج / محمد خيري", "خزينه", "رد مبلغ"],
        ]
        for number, row in enumerate(values, 7):
            for col, value in enumerate(row[:3] + [f"=D{number-1}+B{number}-C{number}"] + row[3:], 1):
                sheet.cell(number, col, value)
        for number in range(13, 18):
            sheet.cell(number, 4, f"=D{number-1}+B{number}-C{number}")
        book.save(self.path)

    def import_file(self):
        return import_libya_workbook(self.path, company=self.company, abbr="T" + self.key[:4])

    def test_parser_dates_and_formula_only_rows(self):
        inspection = inspect_workbook(self.path)
        self.assertEqual(len(inspection["rows"]), 6)
        self.assertEqual(inspection["totals"], dict(incoming=540, outgoing=200, closing_balance=340))
        resolved = resolved_workbook(self.path)["rows"]
        self.assertEqual(resolved[0]["posting_date"], "2026-10-12")
        self.assertEqual(resolved[2]["posting_date"], "2026-10-12")
        self.assertEqual(resolved[2]["display_date"], "")
        self.assertEqual(resolved[3]["posting_date"], "2026-10-13")

    def test_post_reconcile_repeat_export_and_cancel(self):
        result = self.import_file()
        self.assertEqual(result["rows"], 6)
        self.assertEqual(result["counts"], {"Treasury Transaction": 5, "Expense Entry": 1})
        self.assertEqual(result["currency"], "LYD")
        self.assertEqual(get_defaults(self.company)["account"], result["filters"]["account"])
        self.assertEqual(get_defaults(self.company)["batch"], result["batch"])
        self.assertEqual(result["totals"]["closing_balance"], 340)
        balances = {row.account: row.balance for row in result["balances"]}
        advance = frappe.db.get_value("Account", {"company": self.company, "her_treasury_kind": "Employee Advance"}, "name")
        self.assertEqual(balances[advance], 50)
        expense_accounts = frappe.get_all("Account", filters={"company": self.company, "root_type": "Expense", "is_group": 0}, pluck="name")
        self.assertEqual(sum(balances.get(account, 0) for account in expense_accounts), 100)
        self.assertEqual(self.import_file()["journals"], 6)
        self.assertEqual(frappe.db.count("Journal Entry", {"company": self.company}), 6)
        download_workbook(result["filters"])
        from io import BytesIO
        exported = openpyxl.load_workbook(BytesIO(frappe.local.response.filecontent))
        self.assertTrue(exported.active.sheet_view.rightToLeft)
        self.assertEqual(exported.active["D12"].value, 340)
        self.assertEqual(tuple(exported.active.cell(5, i).value for i in range(1, 8)), HEADERS)
        expense = frappe.get_doc("Expense Entry", {"company": self.company, "her_workbook_batch": result["batch"]})
        expense.cancel()
        _, rows, _, _, summary = execute(result["filters"])
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1]["balance"], 440)
        with self.assertRaises(AssertionError):
            self.import_file()  # A partially cancelled import cannot silently repost.

    def test_report_opening_period_permissions_and_wrong_company(self):
        result = self.import_file()
        filters = dict(result["filters"], from_date="2026-10-13", workbook_order=0)
        _, rows, _, _, _ = execute(filters)
        self.assertEqual(rows[0]["balance"], 350)
        self.assertEqual(rows[-1]["balance"], 340)
        with self.assertRaises(frappe.ValidationError):
            execute(dict(filters, company="cranes company"))
        native = frappe.has_permission
        with patch("frappe.has_permission", side_effect=lambda dt, *a, **kw: False if dt == "Journal Entry" else native(dt, *a, **kw)):
            with self.assertRaises(frappe.PermissionError):
                execute(filters)

    def test_failed_posting_rolls_back_whole_import(self):
        from heavy_equipment_rental.expenses import RentalExpenseEntry
        with patch.object(RentalExpenseEntry, "on_submit", side_effect=frappe.ValidationError("Posting denied")):
            with self.assertRaises(frappe.ValidationError):
                self.import_file()
        self.assertFalse(frappe.db.exists("Company", self.company))
        self.assertEqual(frappe.db.count("Journal Entry", {"company": self.company}), 0)

    def test_cost_center_filter_opening_export_and_backfill(self):
        from heavy_equipment_rental.patches.treasury_workbook_cost_centers import execute as backfill

        result = self.import_file()
        center = lambda title: frappe.db.get_value("Cost Center", {
            "company": self.company, "cost_center_name": title,
        }, "name")
        for title, count, incoming, outgoing, balance in (
            ("نسريات", 1, 0, 100, -100), ("سلفة", 1, 0, 50, -50),
            ("خزينه", 3, 540, 20, 520), ("شخصي محمد خيري", 1, 0, 30, -30),
        ):
            filters = dict(result["filters"], cost_center=center(title))
            _, rows, _, _, summary = execute(filters)
            self.assertEqual(len(rows), count)
            self.assertEqual(sum(r["incoming"] for r in rows), incoming)
            self.assertEqual(sum(r["outgoing"] for r in rows), outgoing)
            self.assertEqual(rows[-1]["balance"], balance)
            self.assertTrue(all(r["cost_center"] == center(title) for r in rows))
        filters = dict(result["filters"], cost_center=center("خزينه"), from_date="2026-10-13")
        _, rows, _, _, _ = execute(filters)
        self.assertEqual(rows[0]["balance"], 500)
        self.assertEqual(rows[-1]["balance"], 520)
        download_workbook(dict(result["filters"], cost_center=center("سلفة")))
        from io import BytesIO
        exported = openpyxl.load_workbook(BytesIO(frappe.local.response.filecontent))
        self.assertEqual(exported.active["D7"].value, -50)
        self.assertEqual(exported.active.max_row, 7)
        with self.assertRaises(frappe.ValidationError):
            execute(dict(result["filters"], cost_center=frappe.db.get_value("Company", "cranes company", "cost_center")))

        transfer = frappe.get_doc("Treasury Transaction", {
            "company": self.company, "her_workbook_category": "سلفة",
        })
        ledger_before = frappe.get_all("GL Entry", filters={"company": self.company},
            fields=["name", "account", "cost_center", "debit", "credit"], order_by="name")
        frappe.db.set_value("Treasury Transaction", transfer.name, "cost_center", None)
        backfill()
        self.assertEqual(frappe.db.get_value("Treasury Transaction", transfer.name, "cost_center"), center("سلفة"))
        # Repeating the patch preserves an explicit subsequent assignment.
        frappe.db.set_value("Treasury Transaction", transfer.name, "cost_center", center("نسريات"))
        backfill()
        self.assertEqual(frappe.db.get_value("Treasury Transaction", transfer.name, "cost_center"), center("نسريات"))
        self.assertEqual(ledger_before, frappe.get_all("GL Entry", filters={"company": self.company},
            fields=["name", "account", "cost_center", "debit", "credit"], order_by="name"))

    def test_reject_unsafe_amounts_formulas_and_changed_file(self):
        inspection = inspect_workbook(self.path)
        with self.assertRaises(ValueError):
            import_libya_workbook(self.path, company=self.company, expected_sha256="different")
        book = openpyxl.load_workbook(self.path)
        book.active["B7"] = "=1+500"
        book.save(self.path)
        with self.assertRaises(ValueError):
            inspect_workbook(self.path)
        book.active["B7"] = 500
        book.active["D7"] = "=SUM(B7:C7)"
        book.save(self.path)
        with self.assertRaises(ValueError):
            inspect_workbook(self.path)
