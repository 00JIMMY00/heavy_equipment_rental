"""Accounting integration checks for the rental report and repeatable demo."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from heavy_equipment_rental import demo
from heavy_equipment_rental.heavy_equipment_rental.report.crane_rental_profitability.crane_rental_profitability import execute


class TestCraneRentalProfitability(FrappeTestCase):
    def setUp(self):
        self.location = "HER report test " + frappe.generate_hash(length=8)
        with patch.object(demo, "DEMO_LOCATION", self.location):
            self.cycle = demo.create_rental_cycle("cranes company")
        self.filters = {key: self.cycle[key] for key in ("company", "from_date", "to_date", "assignment")}

    def totals(self):
        result = execute(self.filters)
        return [item["value"] for item in result[4]]

    def test_posted_income_cash_custody_and_repeatable_demo(self):
        result = execute(self.filters)
        self.assertEqual(self.totals(), [15000, 3500, 11500])
        self.assertEqual(len(result[1]), 5)
        expenses = [row for row in result[1] if row["voucher_type"] == "Expense Entry"]
        self.assertEqual(sum(row["expenses"] for row in expenses if "Custody" in row["source_account"]), 1500)
        self.assertEqual(sum(row["expenses"] for row in expenses if "Custody" not in row["source_account"]), 2000)
        # Receipt and custody funding are balance-sheet movements, excluded above.
        invoice = self.cycle["timesheets"][0].sales_invoice
        self.assertEqual(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"), 0)
        with patch.object(demo, "DEMO_LOCATION", self.location):
            self.assertEqual(demo.create_rental_cycle("cranes company")["assignment"], self.cycle["assignment"])
        self.filters["crane"] = self.cycle["crane"]
        self.assertEqual(self.totals(), [15000, 3500, 11500])
        self.filters["from_date"] = self.filters["to_date"] = "2026-10-24"
        self.assertEqual(self.totals(), [0, 0, 0])

    def test_cancelled_and_draft_expenses_and_sales_return(self):
        expense = frappe.get_doc("Expense Entry", self.cycle["expenses"][0])
        amount = sum(row.amount for row in expense.expenses)
        expense.cancel()
        draft = frappe.copy_doc(expense)
        draft.docstatus = 0
        draft.journal_entry = None
        draft.amended_from = expense.name
        draft.insert()
        self.assertEqual(self.totals(), [15000, 3500 - amount, 11500 + amount])
        from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
        credit = make_sales_return(self.cycle["timesheets"][0].sales_invoice)
        credit.set_posting_time = 1
        credit.posting_date = self.cycle["to_date"]
        credit.insert()
        credit.submit()
        self.assertEqual(self.totals(), [0, 3500 - amount, amount - 3500])
        credit.cancel()
        self.assertEqual(self.totals(), [15000, 3500 - amount, 11500 + amount])

    def test_shared_invoice_link_is_counted_once_and_purchase_is_included(self):
        sheet = frappe.get_doc("Crane Timesheet", self.cycle["timesheets"][0].name)
        extra = frappe.get_doc(dict(doctype="Crane Timesheet", assignment=sheet.assignment,
            crane=sheet.crane, driver=sheet.driver, period_start=sheet.period_start, period_end=sheet.period_start,
            timesheet_entries=[dict(work_date=sheet.period_start, start_time="17:00", end_time="18:00")])).insert()
        extra.submit()
        from heavy_equipment_rental.billing import generate_sales_invoice
        self.assertTrue(generate_sales_invoice(timesheet=extra.name)["already_exists"])
        self.assertEqual(self.totals(), [15000, 3500, 11500])
        supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=self.location,
            supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
        crane = frappe.get_doc("Crane", sheet.crane)
        crane.ownership_type, crane.supplier = "Rented", supplier.name
        crane.save()
        purchased = frappe.get_doc(dict(doctype="Crane Timesheet", assignment=sheet.assignment,
            crane=sheet.crane, driver=sheet.driver, period_start=sheet.period_end, period_end=sheet.period_end,
            purchase_rate=700, timesheet_entries=[dict(work_date=sheet.period_end,
                start_time="17:00", end_time="18:00")])).insert()
        purchased.submit()
        purchase = frappe.get_doc("Purchase Invoice", purchased.purchase_invoice)
        # Invoice is posted today by the normal purchasing controller.
        self.filters["to_date"] = purchase.posting_date
        self.assertEqual(self.totals(), [15000, 4200, 10800])
        purchase.cancel()
        self.assertEqual(self.totals(), [15000, 3500, 11500])

    def test_required_filters_and_permissions(self):
        with self.assertRaises(frappe.ValidationError):
            execute({})
        with patch("frappe.has_permission", side_effect=lambda doctype, *args, **kwargs: doctype != "Purchase Invoice"):
            with self.assertRaises(frappe.PermissionError):
                execute(self.filters)

    def test_historical_expenses_with_missing_or_unsubmitted_journals(self):
        missing, deleted, unsubmitted = self.cycle["expenses"][:3]
        excluded_amount = 0
        for name in (missing, deleted, unsubmitted):
            expense = frappe.get_doc("Expense Entry", name)
            excluded_amount += sum(row.amount for row in expense.expenses)
            if name == unsubmitted:
                # Reproduce inconsistent historical data without invoking cancellation.
                frappe.db.set_value("Journal Entry", expense.journal_entry, "docstatus", 0)
            else:
                frappe.db.set_value("Expense Entry", name, "journal_entry",
                                    None if name == missing else "HER-MISSING-JOURNAL")
        result = execute(self.filters)
        self.assertEqual(self.totals(), [15000, 3500 - excluded_amount, 11500 + excluded_amount])
        for name in (missing, deleted, unsubmitted):
            self.assertIn(name, result[2])
            self.assertNotIn(name, [row["voucher"] for row in result[1]])
        self.assertIn("Review these historical records", result[2])
        self.assertIsNone(frappe.db.get_value("Expense Entry", missing, "journal_entry"))
        self.assertEqual(frappe.db.get_value("Expense Entry", deleted, "journal_entry"), "HER-MISSING-JOURNAL")
