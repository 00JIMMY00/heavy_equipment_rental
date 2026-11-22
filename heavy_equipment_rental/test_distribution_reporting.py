"""Reconcile settlement economics, costs and participant balances without postings."""

import json
from unittest.mock import patch

import frappe
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from heavy_equipment_rental.distribution_reporting import execute
from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement import make_partner_payment
from heavy_equipment_rental import test_partner_settlements as partner_tests


class TestDistributionReporting(FrappeTestCase):
    def setUp(self):
        from heavy_equipment_rental.test_expenses import enable_historical_fixtures
        enable_historical_fixtures(self)
        self.fx = partner_tests.TestPartnerSettlements()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)

    def report(self, view="Settlement Summary", **filters):
        return execute(dict(company=self.fx.company.name, report_date=today(), crane=self.fx.crane.name,
                            view=view, **filters))

    @staticmethod
    def details(result):
        return [r for r in result[1] if not r.get("is_total_row")]

    @staticmethod
    def cards(result):
        return {r["label"]: r["value"] for r in result[4]}

    def expense(self, sheet, amounts=(60, 40)):
        template = frappe.get_doc("Grouped Expense", self.fx.cycle["expenses"][0])
        second = frappe.get_doc("Grouped Expense", self.fx.cycle["expenses"][1])
        doc = frappe.get_doc(dict(doctype="Expense Entry", company=self.fx.company.name,
            posting_date=sheet.period_start, crane=sheet.crane, crane_assignment=sheet.assignment,
            crane_timesheet=sheet.name, mode_of_payment=template.mode_of_payment,
            cost_center=self.fx.company.cost_center, description="Report cost breakdown",
            expenses=[dict(expense_entry_type=entry.items[0].expense_entry_type, amount=amount)
                      for entry, amount in zip((template, second), amounts) if amount])).insert()
        doc.submit()
        return doc

    def posted(self, costs=True):
        sheet = self.fx.sheet()
        expense = self.expense(sheet) if costs else None
        invoice = self.fx.invoice(sheet)
        invoice.submit()
        return sheet, invoice, expense

    def test_dashboard_reconciles_report_and_scopes_status_counts(self):
        from heavy_equipment_rental.distribution_dashboard import get_data
        self.posted()
        filters = dict(company=self.fx.company.name, report_date=today(), crane=self.fx.crane.name,
                       view="Distribution Details")
        report = execute(filters)
        result = get_data(filters)
        self.assertEqual(result["rows"], report[1])
        self.assertEqual(result["cards"], report[4])
        self.assertEqual(result["settlement_count"], 1)
        self.assertEqual(result["statuses"], {"Unpaid": 2})
        filtered = get_data(dict(filters, shareholder=self.fx.partners[0].name))
        self.assertEqual(filtered["statuses"], {"Unpaid": 1})
        self.assertEqual(filtered["cards"][0], result["cards"][0])
        self.assertEqual(get_data(dict(filters, payment_status="Paid"))["settlement_count"], 0)
        with patch("frappe.core.doctype.report.report.Report.is_permitted", return_value=False):
            self.assertRaises(frappe.PermissionError, get_data, filters)

    def test_company_operating_residual_cost_burden_and_source_breakdown(self):
        sheet, invoice, expense = self.posted()
        summary = self.report()
        row = self.details(summary)[0]
        self.assertEqual((row["revenue"], row["operating_fee"], row["expenses"], row["residual_pool"]), (8000, 800, 100, 7100))
        self.assertEqual((row["company_operating"], row["company_residual"], row["company_total"], row["external_total"]), (800, 3550, 4350, 3550))
        self.assertEqual(row["outstanding"], 3550)
        distribution = self.report("Distribution Details")
        rows = self.details(distribution)
        ours = next(r for r in rows if r["participant"] == "Our Company")
        self.assertEqual((ours["operating_share"], ours["residual_share"], ours["expense_burden"], ours["total_share"]), (800, 3550, 50, 4350))
        self.assertNotIn("posted_entitlement", ours)
        self.assertEqual(sum(r["expense_burden"] for r in rows), 100)
        self.assertEqual(sum(r["total_share"] for r in rows), 7900)
        self.assertNotIn("profit_percentage", distribution[1][-1])
        sources = self.details(self.report("Source Details"))
        cost_rows = [r for r in sources if r["source_name"] == expense.name]
        self.assertEqual(sorted(r["expenses"] for r in cost_rows), [40, 60])
        self.assertTrue(all(r["expense_type"] for r in cost_rows))
        self.assertEqual(sum(r["revenue"] for r in sources), 8000)
        self.assertEqual(sum(r["expenses"] for r in sources), 100)

    def test_shared_invoice_and_partner_filter_do_not_duplicate_settlement_totals(self):
        first, second = self.fx.sheet(), self.fx.sheet(offset=1, hours=4)
        self.fx.invoice().submit()
        result = self.report()
        self.assertEqual(sum(r["revenue"] for r in self.details(result)), 12000)
        self.assertEqual(self.cards(result)["Posted Settlement Revenue"], 12000)
        self.assertEqual(result[1][-1]["revenue"], 12000)
        partner = self.fx.partners[0].name
        filtered = self.report("Distribution Details", shareholder=partner)
        self.assertEqual(len(self.details(filtered)), 2)
        self.assertEqual({r["shareholder"] for r in self.details(filtered)}, {partner})
        self.assertEqual(self.cards(filtered)["Posted Settlement Revenue"], 12000)
        self.assertEqual(self.cards(filtered)["Filtered Partners Entitlement"], 2700)
        aggregated = self.details(self.report("Participant Summary"))
        self.assertEqual(len(aggregated), 3)
        ours = next(r for r in aggregated if r["participant"] == "Our Company")
        self.assertEqual((ours["operating_share"], ours["residual_share"], ours["total_share"], ours["settlement_count"]), (1200, 5400, 6600, 2))
        self.assertEqual(sum(r["total_share"] for r in aggregated), 12000)
        self.assertNotIn("profit_percentage", ours)

    def test_partial_future_payment_as_of_movements_and_cancellation(self):
        sheet, invoice, _ = self.posted()
        payment = frappe.get_doc(make_partner_payment(sheet.profit_settlement, shareholder=self.fx.partners[0].name))
        payment.update(dict(posting_date=add_days(today(), 1), reference_no="Report future partial", reference_date=today(),
                            paid_amount=500, received_amount=500))
        payment.references[0].allocated_amount = 500
        payment.insert().submit()
        current = self.report()
        self.assertEqual(self.cards(current)["Partner Payments"], 0)
        self.assertEqual(self.cards(current)["Partners Outstanding"], 3550)
        future = execute(dict(company=self.fx.company.name, report_date=add_days(today(), 1), crane=self.fx.crane.name,
                              view="Entitlement Movements", shareholder=self.fx.partners[0].name))
        rows = self.details(future)
        self.assertEqual([(r["increase"], r["decrease"], r["running_balance"]) for r in rows], [(1775, 0, 1775), (0, 500, 1275)])
        self.assertNotIn("running_balance", future[1][-1])
        self.assertEqual(self.cards(future)["Partner Payments"], 500)
        self.assertEqual(self.cards(future)["Partners Outstanding"], 3050)
        payment.cancel()
        self.assertEqual(self.cards(self.report())["Partners Outstanding"], 3550)

    def test_work_overlap_posting_date_assignment_customer_and_status_filters(self):
        sheet, invoice, _ = self.posted()
        by_work = self.report(from_date=sheet.period_start, to_date=sheet.period_end)
        self.assertEqual(len(self.details(by_work)), 1)
        by_posting = self.report(from_date=sheet.period_start, to_date=sheet.period_end, date_basis="Settlement Posting Date")
        self.assertEqual(self.details(by_posting), [])
        self.assertEqual(len(self.details(self.report(assignment=sheet.assignment, customer=invoice.customer))), 1)
        self.assertEqual(self.details(self.report(assignment="unrelated-assignment")), [])
        self.assertEqual(self.details(self.report(payment_status="Paid")), [])
        self.assertEqual(len(self.details(self.report(payment_status="Unpaid"))), 1)
        self.assertEqual(len(self.details(self.report("Distribution Details", participant="Our Company"))), 1)
        with self.assertRaises(frappe.ValidationError):
            self.report(from_date=today(), to_date=add_days(today(), -1))

    def test_drafts_are_separate_estimates_and_reporting_does_not_recalculate(self):
        crane = self.fx.crane
        crane.update(dict(agreement_effective_from=self.fx.start, settlement_approval="Review Before Posting"))
        crane.save()
        sheet, invoice, _ = self.posted(costs=False)
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        self.assertEqual(settlement.docstatus, 0)
        settlement.save()  # Review-mode drafts retain the last explicitly saved calculation.
        snapshot = settlement.agreement_snapshot, settlement.source_snapshot
        counts = {dt: frappe.db.count(dt) for dt in ("GL Entry", "Payment Entry", "Journal Entry")}
        self.assertEqual(self.details(self.report()), [])
        result = self.report(settlement_status="Draft")
        self.assertEqual(self.cards(result)["Posted Settlement Revenue"], 0)
        self.assertEqual(self.cards(result)["Draft Partner Estimates"], 3600)
        self.assertEqual(self.details(result)[0]["posted_entitlement"], 0)
        self.assertEqual(self.details(result)[0]["pending_entitlement"], 3600)
        self.assertEqual(self.details(self.report("Entitlement Movements", settlement_status="Draft")), [])
        settlement.reload()
        self.assertEqual((settlement.agreement_snapshot, settlement.source_snapshot), snapshot)
        self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})

    def test_snapshot_percentages_and_independent_ownership_and_profit(self):
        crane = self.fx.crane
        crane.agreement_effective_from = self.fx.start
        for share in crane.ownership_partners:
            share.profit_percentage = 20 if share.is_company else 40
        crane.save()
        sheet, invoice, _ = self.posted()
        before = self.details(self.report("Distribution Details"))
        ours = next(r for r in before if r["participant"] == "Our Company")
        self.assertEqual((ours["ownership_percentage"], ours["profit_percentage"], ours["expense_burden"]), (50, 20, 20))
        crane.agreement_effective_from = add_days(today(), 1)
        crane.operating_percentage = 15
        crane.save()
        self.assertEqual(self.details(self.report("Distribution Details")), before)

    def test_denied_sources_or_payment_documents_fail_instead_of_partial_totals(self):
        sheet, invoice, _ = self.posted()
        self.fx.pay(frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement), amount=500)
        original = Document.check_permission
        for denied in ("Sales Invoice", "Payment Entry"):
            def deny(doc, *args, **kwargs):
                if doc.doctype == denied:
                    raise frappe.PermissionError
                return original(doc, *args, **kwargs)
            with patch.object(Document, "check_permission", deny), self.assertRaises(frappe.PermissionError):
                self.report()


    def test_mixed_posted_and_draft_totals_and_non_cash_adjustments_stay_separate(self):
        sheet, invoice, _ = self.posted(costs=False)
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        payable = json.loads(settlement.agreement_snapshot)["payable_account"]
        adjustment = frappe.get_doc(dict(doctype="Journal Entry", company=self.fx.company.name,
            posting_date=today(), accounts=[
                dict(account=payable, party_type="Shareholder", party=self.fx.partners[0].name,
                     debit_in_account_currency=500, reference_type="Journal Entry", reference_name=settlement.journal_entry),
                dict(account=self.fx.company.default_expense_account, credit_in_account_currency=500,
                     cost_center=self.fx.company.cost_center)])).insert()
        adjustment.submit()
        cards = self.cards(self.report())
        self.assertEqual((cards["Partner Payments"], cards["Other Partner Adjustments"], cards["Partners Outstanding"]), (0, 500, 3100))
        self.fx.crane.update(dict(agreement_effective_from=add_days(self.fx.start, 1), settlement_approval="Review Before Posting"))
        self.fx.crane.save()
        second = self.fx.sheet(offset=1, hours=4)
        self.fx.invoice(second).submit()
        frappe.get_doc("Crane Profit Settlement", second.profit_settlement).save()
        result = self.report(settlement_status="All")
        totals = [r for r in result[1] if r.get("is_total_row")]
        self.assertEqual(len(totals), 2)
        self.assertEqual(sorted(r["revenue"] for r in totals), [4000, 8000])
        chart = result[3]["data"]
        self.assertEqual(len(chart["labels"]), 2)
        self.assertEqual(set(chart["labels"]), {f"{self.fx.crane.crane_name} · {r['settlement_status']}" for r in self.details(result)})
        self.assertEqual(sorted(chart["datasets"][1]["values"]), [1800, 3600])
        self.assertEqual(self.cards(result)["Posted Settlement Revenue"], 8000)
        self.assertEqual(self.cards(result)["Draft Partner Estimates"], 1800)


    def test_one_cent_cost_burden_matches_actual_rounded_residual_difference(self):
        self.fx.crane.update(dict(agreement_effective_from=self.fx.start, operating_percentage=0))
        self.fx.crane.save()
        self.fx.assignment.assigned_cranes[0].rental_rate = 0.02
        self.fx.assignment.save()
        sheet = self.fx.sheet(hours=1)
        self.expense(sheet, amounts=(0.01, 0))
        self.fx.invoice(sheet).submit()
        rows = self.details(self.report("Distribution Details"))
        ours = next(r for r in rows if r["participant"] == "Our Company")
        self.assertEqual((ours["residual_before_costs"], ours["residual_share"], ours["expense_burden"]), (0.01, 0.01, 0))
        self.assertEqual(sum(r["expense_burden"] for r in rows), 0.01)
        self.assertEqual(sum(r["residual_before_costs"] for r in rows), 0.02)
        self.assertEqual(sum(r["residual_share"] for r in rows), 0.01)
