"""Real ledgers, period locks, payments, agreement history and deficit rejection."""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt

from heavy_equipment_rental import demo
from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement import make_partner_payment
from heavy_equipment_rental.profit_sharing import collect_sources, settlement_defaults


class TestCraneProfitSettlement(FrappeTestCase):
    def setUp(self):
        self.key = frappe.generate_hash(length=8)
        with patch.object(demo, "DEMO_LOCATION", "HER settlement " + self.key):
            self.cycle = demo.create_rental_cycle("cranes company")
        self.company = frappe.get_doc("Company", self.cycle["company"])
        self.crane = frappe.get_doc("Crane", self.cycle["crane"])
        self.supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name="HER Partner " + self.key,
            supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
        self.crane.update(dict(ownership_type="Shared Ownership", sharing_company=self.company.name,
            agreement_effective_from=self.cycle["from_date"],
            profit_allocation_account=self.company.default_expense_account,
            partner_payable_account=self.company.default_payable_account,
            sharing_cost_center=self.company.cost_center))
        self.crane.set("ownership_partners", [
            dict(is_company=1, ownership_percentage=25, profit_percentage=60),
            dict(supplier=self.supplier.name, ownership_percentage=75, profit_percentage=40),
        ])
        self.crane.save()

    def settlement(self, start=None, end=None):
        return frappe.get_doc(dict(doctype="Crane Profit Settlement", crane=self.crane.name,
            from_date=start or self.cycle["from_date"], to_date=end or self.cycle["to_date"],
            posting_date=end or self.cycle["to_date"])).insert()

    def journal(self, amount, day, income=False):
        return frappe.get_doc(dict(doctype="Journal Entry", company=self.company.name,
            posting_date=day, accounts=[
                dict(account=self.company.default_income_account if income else self.company.default_expense_account,
                     crane=self.crane.name, cost_center=self.company.cost_center,
                     **{"credit_in_account_currency" if income else "debit_in_account_currency": amount}),
                dict(account=self.company.default_cash_account,
                     **{"debit_in_account_currency" if income else "credit_in_account_currency": amount}),
            ])).insert()

    def test_posting_independent_shares_and_native_partial_payments(self):
        doc = self.settlement()
        self.assertEqual((doc.revenue, doc.operating_expenses, doc.net_profit), (15000, 3500, 11500))
        self.assertEqual([r.amount for r in doc.shares], [6900, 4600])
        self.assertEqual([r.ownership_percentage for r in doc.shares], [25, 75])
        doc.submit()
        journal = frappe.get_doc("Journal Entry", doc.journal_entry)
        self.assertEqual(journal.docstatus, 1)
        self.assertEqual(journal.total_debit, 4600)
        self.assertEqual(journal.accounts[0].account,
                         frappe.get_doc("Sales Invoice", self.cycle["timesheets"][0].sales_invoice).items[0].income_account)
        self.assertNotIn(self.company.default_expense_account, [r.account for r in journal.accounts])
        self.assertNotIn(self.company.default_cash_account, [r.account for r in journal.accounts])
        self.assertEqual((journal.accounts[1].party_type, journal.accounts[1].party), ("Shareholder", self.crane.ownership_partners[1].shareholder))
        self.assertEqual(frappe.db.count("GL Entry", {"voucher_no": journal.name, "is_cancelled": 0}), 2)
        payment = frappe.get_doc(make_partner_payment(doc.name, self.supplier.name))
        self.assertTrue(payment.is_new())
        self.assertEqual(payment.paid_amount, 4600)
        payment.paid_amount = payment.received_amount = payment.references[0].allocated_amount = 1000
        payment.reference_no, payment.reference_date = "HER partial", doc.posting_date
        payment.insert()
        payment.submit()
        with self.assertRaises(frappe.ValidationError):
            doc.cancel()
        doc.reload()
        remaining = frappe.get_doc(make_partner_payment(doc.name, self.supplier.name))
        self.assertEqual(remaining.paid_amount, 3600)
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc("Journal Entry", doc.journal_entry).cancel()
        remaining.reference_no, remaining.reference_date = "HER balance", doc.posting_date
        remaining.insert()
        remaining.submit()
        with self.assertRaises(frappe.ValidationError):
            make_partner_payment(doc.name, self.supplier.name)

    def test_multiple_source_income_accounts_returns_and_dimensions(self):
        from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

        income = frappe.get_doc(dict(doctype="Account", account_name="HER revenue " + self.key,
            company=self.company.name, root_type="Income", report_type="Profit and Loss",
            parent_account=frappe.db.get_value("Account", {"company": self.company.name,
                "root_type": "Income", "is_group": 1}, "name"))).insert()
        center = frappe.get_doc(dict(doctype="Cost Center", cost_center_name="HER revenue " + self.key,
            company=self.company.name, parent_cost_center=frappe.db.get_value("Cost Center",
                {"company": self.company.name, "is_group": 1}, "name"))).insert()
        original = frappe.get_doc("Sales Invoice", self.cycle["timesheets"][0].sales_invoice)
        extra = frappe.copy_doc(original)
        extra.docstatus = 0
        extra.items[0].update(dict(qty=3, rate=1000, income_account=income.name, cost_center=center.name))
        extra.insert().submit()
        credit = make_sales_return(extra.name)
        credit.set_posting_time = 1
        credit.posting_date = self.cycle["to_date"]
        credit.items[0].qty = -1
        credit.insert().submit()
        doc = self.settlement()
        self.assertEqual((doc.revenue, doc.operating_expenses, doc.external_distribution), (17000, 3500, 5400))
        doc.submit()
        journal = frappe.get_doc("Journal Entry", doc.journal_entry)
        rows = {r.account: r for r in journal.accounts if not r.party}
        self.assertEqual(rows[original.items[0].income_account].debit_in_account_currency, 4764.71)
        self.assertEqual(rows[income.name].debit_in_account_currency, 635.29)
        self.assertEqual(rows[income.name].cost_center, center.name)
        self.assertEqual(journal.total_debit, journal.total_credit)
        self.assertEqual(frappe.get_doc(make_partner_payment(doc.name, self.supplier.name)).paid_amount, 5400)
        snapshot = doc.source_snapshot
        doc.cancel()
        replacement = frappe.copy_doc(doc, ignore_no_copy=False)
        replacement.docstatus = 0
        replacement.amended_from = doc.name
        replacement.insert().submit()
        self.assertEqual(replacement.source_snapshot, snapshot)
        self.assertEqual(replacement.external_distribution, 5400)
        self.assertEqual(frappe.db.get_value("Journal Entry", journal.name, "docstatus"), 2)

    def test_signed_income_account_allocation_and_invalid_account_rejection(self):
        from heavy_equipment_rental.profit_sharing import revenue_allocation_rows

        first = self.company.default_income_account
        second = frappe.get_doc(dict(doctype="Account", account_name="HER contra " + self.key,
            company=self.company.name, root_type="Income", report_type="Profit and Loss",
            parent_account=frappe.db.get_value("Account", {"company": self.company.name,
                "root_type": "Income", "is_group": 1}, "name"))).insert().name
        sources = [dict(name="income", income_account=first, revenue=100),
                   dict(name="return", income_account=second, revenue=-20)]
        rows = revenue_allocation_rows(sources, 40, self.company.name, self.company.default_currency,
                                       self.company.cost_center, 2)
        amounts = {r["account"]: r["debit_in_account_currency"] - r["credit_in_account_currency"] for r in rows}
        self.assertEqual(amounts, {first: 50, second: -10})
        sources[0]["income_account"] = self.company.default_expense_account
        with self.assertRaisesRegex(frappe.ValidationError, "Income account"):
            revenue_allocation_rows(sources, 40, self.company.name, self.company.default_currency,
                                    self.company.cost_center, 2)

    def test_operating_first_does_not_require_legacy_allocation_account(self):
        self.crane.agreement_effective_from = add_days(self.cycle["to_date"], 1)
        self.crane.profit_allocation_account = None
        self.crane.save()
        self.settlement().submit()
        day = self.crane.agreement_effective_from
        self.journal(1000, day, income=True).submit()
        doc = self.settlement(day, day)
        doc.submit()
        self.assertEqual(frappe.get_doc("Journal Entry", doc.journal_entry).accounts[0].account,
                         self.company.default_income_account)

    def test_duplicate_drafts_cannot_both_submit_and_gaps_are_rejected(self):
        first, duplicate = self.settlement(), self.settlement()
        first.submit()
        with self.assertRaises(frappe.ValidationError):
            duplicate.submit()
        day = add_days(self.cycle["to_date"], 2)
        with self.assertRaises(frappe.ValidationError):
            self.settlement(day, day)
        defaults = settlement_defaults(self.crane.name)
        self.assertEqual(defaults["from_date"], add_days(self.cycle["to_date"], 1))

    def test_expenses_over_balance_block_save_and_submission(self):
        draft = self.settlement()
        self.journal(20000, self.cycle["to_date"]).submit()
        journals = frappe.db.count("Journal Entry")
        with self.assertRaisesRegex(frappe.ValidationError, "8,500.00"):
            self.settlement()
        with self.assertRaisesRegex(frappe.ValidationError, "Settlement stopped"):
            draft.submit()
        draft.reload()
        self.assertEqual(draft.docstatus, 0)
        self.assertFalse(draft.journal_entry)
        self.assertEqual(frappe.db.count("Journal Entry"), journals)
        self.assertFalse(frappe.db.count("Crane Profit Settlement", {"crane": self.crane.name, "docstatus": 1}))

    def test_changed_percentages_are_dated_and_historical_snapshots_survive(self):
        first = self.settlement()
        first.submit()
        snapshot = first.agreement_snapshot
        day = add_days(self.cycle["to_date"], 1)
        self.crane.agreement_effective_from = day
        self.crane.ownership_partners[0].profit_percentage = 30
        self.crane.ownership_partners[1].profit_percentage = 70
        self.crane.save()
        self.assertEqual(len(json.loads(self.crane.agreement_history)), 2)
        first.reload()
        self.assertEqual(first.agreement_snapshot, snapshot)
        first.cancel()
        replacement = self.settlement()
        self.assertEqual([r.amount for r in replacement.shares], [6900, 4600])
        with self.assertRaises(frappe.ValidationError):
            self.settlement(end=day)
        replacement.submit()
        revenue = self.journal(1000, day, income=True)
        revenue.submit()
        second = self.settlement(day, day)
        self.assertEqual([r.amount for r in second.shares], [300, 700])
        with self.assertRaises(frappe.ValidationError):
            self.crane.agreement_history = "[]"
            self.crane.save()

    def test_closed_sources_and_backdated_postings_are_protected(self):
        doc = self.settlement()
        doc.submit()
        for source in (frappe.get_doc("Expense Entry", self.cycle["expenses"][0]),
                       frappe.get_doc("Sales Invoice", self.cycle["timesheets"][0].sales_invoice)):
            with self.assertRaises(frappe.ValidationError):
                source.cancel()
        backdated = self.journal(100, self.cycle["to_date"])
        with self.assertRaises(frappe.ValidationError):
            backdated.submit()
        doc.cancel()
        backdated.reload()
        backdated.submit()

    def test_agreement_validation_and_operator_arrangements(self):
        self.crane.ownership_partners[0].profit_percentage = 80
        with self.assertRaises(frappe.ValidationError):
            self.crane.save()
        self.crane.reload()
        self.crane.agreement_effective_from = add_days(self.cycle["to_date"], 1)
        self.crane.ownership_type = "Operated for Owner"
        self.crane.ownership_partners[0].ownership_percentage = 0
        self.crane.ownership_partners[1].ownership_percentage = 100
        self.crane.save()
        self.crane.agreement_effective_from = add_days(self.cycle["to_date"], 2)
        self.crane.ownership_type = "Operated by Partner"
        self.crane.operating_partner = self.supplier.name
        self.crane.save()
        self.assertEqual(self.crane.operator_type, "External Operator")

    def test_zero_profit_and_rounding_conserve_the_distributed_amount(self):
        extra = self.journal(11500, self.cycle["to_date"])
        extra.submit()
        zero = self.settlement()
        zero.submit()
        self.assertFalse(zero.journal_entry)
        self.assertEqual(zero.distributable_profit, 0)
        day = add_days(self.cycle["to_date"], 1)
        revenue = self.journal(0.01, day, income=True)
        revenue.submit()
        second = self.settlement(day, day)
        self.assertEqual(flt(sum(r.amount for r in second.shares), 2), 0.01)
        self.assertTrue(all(r.amount >= 0 for r in second.shares))

    def test_native_invoice_attribution_and_missing_accounting_permissions(self):
        from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

        invoice = frappe.get_doc("Sales Invoice", self.cycle["timesheets"][0].sales_invoice)
        self.assertEqual(invoice.items[0].crane, self.crane.name)
        credit = make_sales_return(invoice.name)
        credit.set_posting_time = 1
        credit.posting_date = self.cycle["to_date"]
        credit.insert()
        credit.submit()
        with self.assertRaisesRegex(frappe.ValidationError, "Settlement stopped"):
            self.settlement()
        permission = frappe.permissions.has_permission

        def deny(doctype, *args, **kwargs):
            if doctype == "Journal Entry" and (kwargs.get("ptype") or (args[0] if args else None)) == "read":
                if kwargs.get("throw"):
                    raise frappe.PermissionError
                return False
            return permission(doctype, *args, **kwargs)

        with patch("frappe.permissions.has_permission", side_effect=deny), self.assertRaises(frappe.PermissionError):
            collect_sources(self.crane.name, self.company.name, self.cycle["from_date"], self.cycle["to_date"])

    def test_migration_is_repeatable_and_leaves_legacy_cranes_unconfigured(self):
        from heavy_equipment_rental.patches.add_crane_profit_sharing import execute

        legacy = frappe.get_doc(dict(doctype="Crane", crane_name="HER legacy " + self.key, ownership_type="Other")).insert()
        before = self.crane.agreement_history
        execute()
        execute()
        self.crane.reload()
        legacy.reload()
        self.assertEqual(self.crane.agreement_history, before)
        self.assertEqual(legacy.ownership_type, "Other")
        self.assertFalse(legacy.agreement_history)

    def test_native_tagged_invoices_and_journals_are_counted_once(self):
        original = frappe.get_doc("Sales Invoice", self.cycle["timesheets"][0].sales_invoice)
        invoice = frappe.copy_doc(original)
        invoice.docstatus = 0
        invoice.insert()
        invoice.submit()
        purchase = frappe.get_doc(dict(doctype="Purchase Invoice", company=self.company.name,
            supplier=self.supplier.name, posting_date=self.cycle["to_date"], set_posting_time=1,
            items=[dict(item_code=self.crane.item, crane=self.crane.name, qty=1, rate=500,
                        uom="Hour", conversion_factor=1)], taxes=[])).insert()
        purchase.submit()
        journal = self.journal(1000, self.cycle["to_date"])
        journal.submit()
        doc = self.settlement()
        self.assertEqual((doc.revenue, doc.operating_expenses), (30000, 5000))
        doc.revenue = 999999
        doc.agreement_snapshot = "{}"
        doc.save()
        self.assertEqual(doc.revenue, 30000)
        self.assertEqual(len(doc.shares), 2)
        doc.submit()
        next_day = add_days(self.cycle["to_date"], 1)
        self.assertEqual(self.settlement(next_day, next_day).net_profit, 0)

    def test_invalid_historical_expense_blocks_settlement(self):
        frappe.db.set_value("Expense Entry", self.cycle["expenses"][0], "journal_entry", None)
        with self.assertRaises(frappe.ValidationError):
            self.settlement()

    def test_many_partners_and_dated_pause(self):
        other = frappe.copy_doc(self.supplier)
        other.supplier_name += " second"
        other.insert()
        day = add_days(self.cycle["to_date"], 1)
        self.crane.agreement_effective_from = day
        self.crane.ownership_partners[1].profit_percentage = 30
        self.crane.append("ownership_partners", dict(supplier=other.name,
            ownership_percentage=0, profit_percentage=10))
        self.crane.save()
        first = self.settlement()
        first.submit()
        self.journal(1000, day, income=True).submit()
        second = self.settlement(day, day)
        self.assertEqual([r.amount for r in second.shares], [600, 300, 100])
        second.submit()
        self.assertEqual(len(frappe.get_doc("Journal Entry", second.journal_entry).accounts), 3)
        self.crane.agreement_effective_from = add_days(day, 1)
        self.crane.enable_profit_sharing = 0
        self.crane.ownership_type = "Owned"
        self.crane.save()
        self.crane.agreement_effective_from = add_days(day, 3)
        self.crane.enable_profit_sharing = 1
        self.crane.save()
        defaults = settlement_defaults(self.crane.name)
        self.assertEqual(defaults["from_date"], add_days(day, 3))
        resumed = self.settlement(defaults["from_date"], defaults["from_date"])
        resumed.submit()

    def test_denied_journal_creation_rolls_back_settlement(self):
        doc = self.settlement()
        permission = frappe.permissions.has_permission

        def deny(doctype, *args, **kwargs):
            ptype = kwargs.get("ptype") or (args[0] if args else "read")
            if doctype == "Journal Entry" and ptype in ("create", "submit"):
                if kwargs.get("throw"):
                    raise frappe.PermissionError
                return False
            return permission(doctype, *args, **kwargs)

        frappe.db.savepoint("denied_profit_posting")
        with patch("frappe.permissions.has_permission", side_effect=deny), self.assertRaises(frappe.PermissionError):
            doc.submit()
        frappe.db.rollback(save_point="denied_profit_posting")
        doc.reload()
        self.assertEqual(doc.docstatus, 0)
        self.assertFalse(doc.journal_entry)

    def test_owner_zero_profit_requires_explicit_confirmation(self):
        history = self.crane.agreement_history
        self.crane.agreement_effective_from = add_days(self.cycle["from_date"], 1)
        self.crane.ownership_partners[0].profit_percentage = 100
        self.crane.ownership_partners[1].profit_percentage = 0
        with self.assertRaisesRegex(frappe.ValidationError, "0% Remaining Balance"):
            self.crane.save()
        self.assertEqual(frappe.db.get_value("Crane", self.crane.name, "agreement_history"), history)
        self.crane.reload()
        self.crane.agreement_effective_from = add_days(self.cycle["from_date"], 1)
        self.crane.ownership_partners[0].profit_percentage = 100
        self.crane.ownership_partners[1].profit_percentage = 0
        self.crane.ownership_partners[1].allow_zero_profit_share = 1
        self.crane.save()
        self.assertEqual(json.loads(self.crane.agreement_history)[-1]["partners"][1]["allow_zero_profit_share"], 1)

    def test_corrected_profit_split_creates_partner_payable(self):
        self.settlement().submit()
        day = add_days(self.cycle["to_date"], 1)
        self.crane.agreement_effective_from = day
        for row, percentage in zip(self.crane.ownership_partners, (60, 40)):
            row.ownership_percentage = row.profit_percentage = percentage
        self.crane.operating_percentage = 10
        self.crane.save()
        self.journal(3000, day, income=True).submit()
        doc = self.settlement(day, day)
        doc.submit()
        partner = next(row for row in doc.shares if not row.is_company)
        self.assertEqual(partner.amount, 1080)
        self.assertTrue(doc.journal_entry)

    def test_large_partner_journal_posts_and_reverses_in_the_same_transaction(self):
        first = self.settlement()
        first.submit()
        day = add_days(self.cycle["to_date"], 1)
        self.crane.agreement_effective_from = day
        self.crane.set("ownership_partners", [dict(is_company=1, ownership_percentage=100,
            profit_percentage=0, allow_zero_profit_share=1)])
        for index in range(100):
            partner = frappe.copy_doc(self.supplier)
            partner.supplier_name += " large " + str(index)
            partner.insert()
            self.crane.append("ownership_partners", dict(supplier=partner.name,
                ownership_percentage=0, profit_percentage=1))
        self.crane.save()
        self.journal(1000, day, income=True).submit()
        doc = self.settlement(day, day)
        doc.submit()
        journal = frappe.get_doc("Journal Entry", doc.journal_entry)
        self.assertEqual((len(journal.accounts), journal.docstatus, journal.total_debit), (101, 1, 1000))
        self.assertEqual(frappe.db.count("GL Entry", {"voucher_no": journal.name, "is_cancelled": 0}), 101)
        doc.cancel()
        self.assertEqual(frappe.db.get_value("Journal Entry", journal.name, "docstatus"), 2)

    def configure_operating(self, *, external=False, company_residual=0):
        self.crane.agreement_effective_from = add_days(self.cycle["from_date"], 1)
        self.crane.operating_percentage = 10
        self.crane.operator_type = "External Operator" if external else "Our Company"
        self.crane.operating_partner = self.supplier.name if external else None
        self.crane.ownership_partners[0].profit_percentage = company_residual
        self.crane.ownership_partners[0].allow_zero_profit_share = int(company_residual == 0)
        self.crane.ownership_partners[1].profit_percentage = 100 - company_residual
        self.crane.save()
        self.settlement(end=self.cycle["from_date"]).submit()
        return self.crane.agreement_effective_from

    def test_operating_first_single_owner_without_company_in_partner_table(self):
        day = self.configure_operating()
        # A zero-ownership operator does not need a row in the owners table.
        self.crane.agreement_effective_from = add_days(day, 1)
        self.crane.set("ownership_partners", [dict(supplier=self.supplier.name,
            ownership_percentage=100, profit_percentage=100)])
        self.crane.save()
        self.settlement(day, day).submit()
        doc = self.settlement(add_days(day, 1))
        self.assertEqual((doc.revenue, doc.operating_fee, doc.balance_after_operating,
                          doc.operating_expenses, doc.distributable_profit), (15000, 1500, 13500, 3500, 10000))
        self.assertEqual([(r.operating_amount, r.residual_amount, r.amount) for r in doc.shares],
                         [(0, 10000, 10000), (1500, 0, 1500)])
        doc.submit()
        self.assertEqual(frappe.get_doc("Journal Entry", doc.journal_entry).total_debit, 10000)

    def test_company_can_receive_both_operating_share_and_residual(self):
        original_history = json.loads(self.crane.agreement_history)
        # Adding company ownership to an owner-operated agreement should
        # classify it as shared without dropping either entitlement.
        self.crane.ownership_type = "Operated for Owner"
        day = self.configure_operating(company_residual=20)
        self.crane.reload()
        self.assertEqual(self.crane.ownership_type, "Shared Ownership")
        self.assertEqual(self.crane.operator_type, "Our Company")
        history = json.loads(self.crane.agreement_history)
        self.assertEqual(history[:-1], original_history)
        self.assertEqual(history[-1]["ownership_type"], "Shared Ownership")
        self.assertEqual(history[-1]["operating_percentage"], 10)
        self.assertEqual(history[-1]["partners"][0]["ownership_percentage"], 25)
        self.assertEqual(history[-1]["partners"][0]["profit_percentage"], 20)
        doc = self.settlement(day)
        self.assertEqual([(r.operating_amount, r.residual_amount, r.amount) for r in doc.shares],
                         [(1500, 2000, 3500), (0, 8000, 8000)])
        self.assertEqual(doc.company_retained, 3500)
        self.assertEqual(doc.external_distribution, 8000)
        self.assertEqual(sum(r.amount for r in doc.shares) + doc.operating_expenses, doc.revenue)
        doc.submit()
        self.assertEqual(frappe.get_doc("Journal Entry", doc.journal_entry).total_debit, 8000)

    def test_company_ownership_classification_still_requires_a_new_effective_date(self):
        original_history = self.crane.agreement_history
        self.crane.agreement_effective_from = add_days(self.cycle["from_date"], 1)
        self.crane.ownership_type = "Operated for Owner"
        self.crane.ownership_partners[0].ownership_percentage = 0
        self.crane.ownership_partners[1].ownership_percentage = 100
        self.crane.operating_percentage = 10
        self.crane.save()
        external_history = self.crane.agreement_history
        self.assertEqual(self.crane.ownership_type, "Operated for Owner")
        self.crane.ownership_partners[0].ownership_percentage = 25
        self.crane.ownership_partners[1].ownership_percentage = 75
        with self.assertRaisesRegex(frappe.ValidationError, "effective date"):
            self.crane.save()
        self.crane.reload()
        self.assertEqual(self.crane.ownership_type, "Operated for Owner")
        self.assertEqual(self.crane.agreement_history, external_history)
        self.assertEqual(json.loads(external_history)[:-1], json.loads(original_history))

    def test_external_operator_receives_operating_and_residual_in_one_payable(self):
        day = self.configure_operating(external=True, company_residual=60)
        doc = self.settlement(day)
        self.assertEqual([(r.operating_amount, r.residual_amount, r.amount) for r in doc.shares],
                         [(0, 6000, 6000), (1500, 4000, 5500)])
        doc.submit()
        payment = frappe.get_doc(make_partner_payment(doc.name, self.supplier.name))
        self.assertEqual(payment.paid_amount, 5500)
        self.assertEqual(frappe.get_doc("Journal Entry", doc.journal_entry).total_debit, 5500)

    def test_operating_fee_survives_zero_residual_but_one_cent_deficit_blocks(self):
        day = self.configure_operating(external=True)
        draft = self.settlement(day)
        self.journal(10000, self.cycle["to_date"]).submit()
        draft.save()
        self.assertEqual((draft.distributable_profit, draft.external_distribution), (0, 1500))
        self.journal(0.01, self.cycle["to_date"]).submit()
        with self.assertRaisesRegex(frappe.ValidationError, "0.01"):
            draft.submit()
        draft.reload()
        self.assertEqual(draft.docstatus, 0)
        self.assertFalse(draft.journal_entry)

    def test_grand_total_allocation_includes_tax_without_duplicating_other_cranes(self):
        from heavy_equipment_rental.profit_sharing import allocate_amount
        original = frappe.get_doc("Sales Invoice", self.cycle["timesheets"][0].sales_invoice)
        other = frappe.get_doc(dict(doctype="Crane", crane_name="HER allocation " + self.key)).insert()
        invoice = frappe.copy_doc(original)
        invoice.docstatus = 0
        invoice.set("items", [dict(item_code=self.crane.item, crane=self.crane.name, qty=1,
                                   rate=6000, uom="Hour", conversion_factor=1),
                              dict(item_code=other.item, crane=other.name, qty=1,
                                   rate=4000, uom="Hour", conversion_factor=1)])
        tax_account = frappe.db.get_value("Account", {"company": self.company.name,
            "account_type": "Tax", "is_group": 0, "disabled": 0}, "name")
        self.assertTrue(tax_account)
        invoice.apply_discount_on = "Net Total"
        invoice.discount_amount = 1000
        invoice.append("taxes", dict(charge_type="On Net Total", account_head=tax_account,
                                     description="HER test tax", rate=10, cost_center=self.company.cost_center))
        invoice.insert()
        invoice.submit()
        ours = collect_sources(self.crane.name, self.company.name, self.cycle["from_date"],
                               self.cycle["to_date"], grand_total=True)
        theirs = collect_sources(other.name, self.company.name, self.cycle["from_date"],
                                 self.cycle["to_date"], grand_total=True)
        self.assertEqual(sum(r.get("revenue", 0) for r in ours if r["name"] == invoice.name), 5940)
        self.assertEqual(sum(r.get("revenue", 0) for r in theirs), 3960)
        self.assertEqual(invoice.base_grand_total, 9900)
        from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
        credit = make_sales_return(invoice.name)
        credit.set_posting_time = 1
        credit.posting_date = self.cycle["to_date"]
        credit.insert()
        credit.submit()
        ours = collect_sources(self.crane.name, self.company.name, self.cycle["from_date"],
                               self.cycle["to_date"], grand_total=True)
        self.assertEqual(sum(r.get("revenue", 0) for r in ours if r["name"] in (invoice.name, credit.name)), 0)
        self.assertEqual(sum(allocate_amount(-0.01, [-1, -1, -1], 2)), -0.01)
        with self.assertRaises(frappe.ValidationError):
            allocate_amount(10, [0, 0], 2)

    def test_operating_percentage_versions_and_legacy_migration_preserve_history(self):
        from heavy_equipment_rental.patches.operating_first_agreements import execute
        history = json.loads(self.crane.agreement_history)
        for version in history:
            version.pop("calculation_method", None)
            version.pop("operating_percentage", None)
        snapshot = json.dumps(history)
        frappe.db.set_value("Crane", self.crane.name, "agreement_history", snapshot)
        execute()
        execute()
        self.crane.reload()
        self.assertEqual(self.crane.sharing_calculation, "Legacy Net Profit")
        self.crane.save()
        self.assertEqual(self.crane.agreement_history, snapshot)
        old = self.settlement()
        old.submit()
        self.assertEqual(frappe.get_doc("Journal Entry", old.journal_entry).accounts[0].account,
                         self.company.default_expense_account)
        old_agreement_snapshot = old.agreement_snapshot
        old_amounts = [r.amount for r in old.shares]
        old_sources = old.source_snapshot
        frappe.db.set_value("Crane Profit Settlement", old.name, "calculation_method", None)
        for row in old.shares:
            frappe.db.set_value("Crane Settlement Share", row.name, "residual_amount", 0)
        execute()
        execute()
        old.reload()
        self.assertEqual(old.calculation_method, "Legacy Net Profit")
        self.assertEqual([r.residual_amount for r in old.shares], old_amounts)
        self.assertEqual([r.amount for r in old.shares], old_amounts)
        self.assertEqual(old.source_snapshot, old_sources)
        self.assertEqual(old.docstatus, 1)
        self.crane.agreement_effective_from = add_days(self.cycle["to_date"], 1)
        self.crane.sharing_calculation = "Operating First"
        self.crane.operating_percentage = 12.5
        self.crane.save()
        execute()
        self.crane.reload()
        self.assertEqual(self.crane.operating_percentage, 12.5)
        old.reload()
        self.assertEqual(old.agreement_snapshot, old_agreement_snapshot)
        day = self.crane.agreement_effective_from
        self.journal(1000, day, income=True).submit()
        new = self.settlement(day, day)
        self.assertEqual((new.operating_fee, new.distributable_profit), (125, 875))

    def test_operating_percentage_rejects_invalid_and_nonfinite_values(self):
        for value in (-1, 100.01, float("nan"), float("inf")):
            self.crane.operating_percentage = value
            with self.assertRaisesRegex(frappe.ValidationError, "finite numbers"):
                self.crane.save()
            self.crane.reload()

    def test_negative_revenue_stops_new_period(self):
        self.settlement().submit()
        day = add_days(self.cycle["to_date"], 1)
        reversal = self.journal(100, day, income=True)
        for row in reversal.accounts:
            row.debit_in_account_currency, row.credit_in_account_currency = (
                row.credit_in_account_currency, row.debit_in_account_currency)
        reversal.save()
        reversal.submit()
        with self.assertRaisesRegex(frappe.ValidationError, "negative revenue"):
            self.settlement(day, day)
