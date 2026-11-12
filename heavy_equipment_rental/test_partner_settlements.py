"""Automatic accrual, real Shareholder payments and as-of-date partner reports."""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from heavy_equipment_rental import demo
from heavy_equipment_rental.billing import generate_sales_invoice
from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement import make_partner_payment
from heavy_equipment_rental.partner_accounts import default_account
from heavy_equipment_rental.partner_reporting import execute_report, settlement_payment_details
from heavy_equipment_rental.timesheet_settlement import ensure_settlement


class TestPartnerSettlements(FrappeTestCase):
    def setUp(self):
        self.key = frappe.generate_hash(length=8)
        with patch.object(demo, "DEMO_LOCATION", "HER auto settlement " + self.key):
            self.cycle = demo.create_rental_cycle("cranes company")
        self.company = frappe.get_doc("Company", self.cycle["company"])
        self.crane = frappe.get_doc("Crane", self.cycle["crane"])
        self.partners = [frappe.get_doc(dict(doctype="Shareholder", title="HER owner " + self.key + str(i),
            company=self.company.name)).insert() for i in range(2)]
        self.crane.update(dict(ownership_type="Shared Ownership", sharing_company=self.company.name,
            agreement_effective_from=self.cycle["from_date"], operating_percentage=10))
        self.crane.set("ownership_partners", [dict(is_company=1, ownership_percentage=50, profit_percentage=50)] + [
            dict(shareholder=p.name, ownership_percentage=25, profit_percentage=25) for p in self.partners])
        self.crane.save()
        self.start = add_days(self.cycle["to_date"], 1)
        self.assignment = frappe.get_doc(dict(doctype="Crane Assignment", company=self.company.name,
            customer=frappe.get_doc("Crane Assignment", self.cycle["assignment"]).customer,
            location="HER auto " + self.key, assigned_cranes=[dict(crane=self.crane.name,
                start_date=self.start, expected_end_date=add_days(self.start, 4), rental_rate_unit="Hour", rental_rate=1000)])).insert()

    def sheet(self, offset=0, hours=8):
        day = add_days(self.start, offset)
        sheet = frappe.get_doc(dict(doctype="Crane Timesheet", assignment=self.assignment.name,
            crane=self.crane.name, period_start=day, period_end=day,
            driver=frappe.db.get_value("Crane Timesheet", self.cycle["timesheets"][0].name, "driver"),
            timesheet_entries=[dict(work_date=day, start_time="08:00", end_time=f"{8 + hours:02}:00")])).insert()
        sheet.submit()
        sheet.reload()
        return sheet

    def invoice(self, sheet=None):
        result = generate_sales_invoice(timesheet=sheet.name) if sheet else generate_sales_invoice(assignment=self.assignment.name)
        return frappe.get_doc("Sales Invoice", result["name"])

    def pay(self, settlement, index=0, amount=None):
        payment = frappe.get_doc(make_partner_payment(settlement.name, shareholder=self.partners[index].name))
        if amount is not None:
            payment.paid_amount = payment.received_amount = payment.references[0].allocated_amount = amount
        payment.reference_no, payment.reference_date = "HER auto payment", today()
        payment.insert().submit()
        return payment

    def test_automatic_submission_and_shareholder_payments(self):
        sheet = self.sheet()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        self.assertEqual((settlement.docstatus, settlement.crane, settlement.timesheet), (0, sheet.crane, sheet.name))
        _, pending, _ = execute_report(dict(company=self.company.name, report_date=today(),
            crane=self.crane.name), summary=True)
        self.assertEqual({r["status"] for r in pending}, {"Awaiting Invoice"})
        invoice = self.invoice(sheet)
        invoice.submit()
        settlement.reload()
        self.assertEqual((settlement.docstatus, settlement.sales_invoice, settlement.revenue), (1, invoice.name, 8000))
        self.assertEqual((settlement.operating_fee, settlement.external_distribution), (800, 3600))
        journal = frappe.get_doc("Journal Entry", settlement.journal_entry)
        self.assertEqual(journal.total_debit, 3600)
        self.assertEqual({r.party_type for r in journal.accounts if r.party}, {"Shareholder"})
        self.assertEqual(journal.accounts[-1].account, default_account(self.company.name))
        self.pay(settlement, amount=500)
        details = settlement_payment_details(settlement.name)
        self.assertEqual((details["balances"][0]["paid_amount"], details["balances"][0]["outstanding_amount"]), (500, 1300))
        self.assertEqual(details["balances"][0]["status"], "Partly Paid")
        self.assertEqual(len(details["payments"]), 1)
        payment = frappe.get_doc(make_partner_payment(settlement.name, shareholder=self.partners[0].name))
        self.assertEqual((payment.payment_type, payment.party_type, payment.paid_amount), ("Pay", "Shareholder", 1300))
        self.assertEqual((payment.crane_profit_settlement, payment.crane_timesheet, payment.crane), (settlement.name, sheet.name, sheet.crane))
        with self.assertRaises(frappe.ValidationError):
            invoice.cancel()
        with self.assertRaises(frappe.ValidationError):
            settlement.cancel()
        ensure_settlement(sheet.reload())
        self.assertEqual(frappe.db.count("Crane Profit Settlement", {"timesheet": sheet.name, "docstatus": ["!=", 2]}), 1)

    def test_shared_invoice_allocates_once_and_reports_real_movements(self):
        first, second = self.sheet(hours=8), self.sheet(offset=1, hours=4)
        invoice = self.invoice()
        invoice.submit()
        settlements = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        self.assertEqual([s.revenue for s in settlements], [8000, 4000])
        self.assertEqual(sum(s.external_distribution for s in settlements), 5400)
        payment = self.pay(settlements[0], amount=500)
        filters = dict(company=self.company.name, report_date=today(), crane=self.crane.name)
        _, detailed, _ = execute_report(filters)
        _, summary, _ = execute_report(filters, summary=True)
        self.assertEqual(sum(r.get("invoice_value", 0) for r in detailed), 12000)
        self.assertEqual(sum(r.get("entitlement", 0) for r in detailed), 5400)
        self.assertEqual(sum(r.get("paid_amount", 0) for r in detailed), 500)
        self.assertEqual(sum(r["outstanding_amount"] for r in summary), 4900)
        self.assertEqual(sum(r["invoice_value"] for r in summary), 12000)
        self.assertEqual(len(summary), 2)
        self.assertIn(payment.name, [r.get("voucher_no") for r in detailed])
        payment.cancel()
        _, summary, _ = execute_report(filters, summary=True)
        self.assertEqual(sum(r["outstanding_amount"] for r in summary), 5400)

    def test_deficit_rolls_back_invoice_and_entitlements(self):
        sheet = self.sheet()
        frappe.get_doc(dict(doctype="Journal Entry", company=self.company.name, posting_date=sheet.period_start,
            accounts=[dict(account=self.company.default_expense_account, debit_in_account_currency=9000,
                cost_center=self.company.cost_center, crane=self.crane.name),
                dict(account=self.company.default_cash_account, credit_in_account_currency=9000)])).insert().submit()
        invoice = self.invoice(sheet)
        frappe.db.savepoint("auto_deficit")
        with self.assertRaisesRegex(frappe.ValidationError, "Settlement stopped"):
            invoice.submit()
        frappe.db.rollback(save_point="auto_deficit")
        self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "docstatus"), 0)
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        self.assertEqual(settlement.docstatus, 0)
        self.assertFalse(settlement.journal_entry)

    def test_settled_timesheet_is_immutable_and_duplicate_is_rejected(self):
        sheet = self.sheet()
        self.invoice(sheet).submit()
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(dict(doctype="Crane Profit Settlement", timesheet=sheet.name, posting_date=today())).insert()
        with self.assertRaises(frappe.ValidationError):
            sheet.cancel()
        with self.assertRaises(frappe.ValidationError):
            make_partner_payment(sheet.profit_settlement, shareholder="unknown")

    def test_payment_link_validation_and_historical_report_date(self):
        sheet = self.sheet()
        invoice = self.invoice(sheet)
        invoice.set_posting_time = 1
        invoice.posting_date = self.start
        invoice.due_date = self.start
        with patch("heavy_equipment_rental.timesheet_settlement.today", return_value=self.start):
            invoice.submit()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        payment = frappe.get_doc(make_partner_payment(settlement.name, shareholder=self.partners[0].name))
        payment.payment_type = "Receive"
        with self.assertRaises(frappe.ValidationError):
            payment.insert()
        self.pay(settlement)
        _, past, _ = execute_report(dict(company=self.company.name, report_date=self.start,
            crane=self.crane.name), summary=True)
        self.assertEqual(sum(r["paid_amount"] for r in past), 0)
        self.assertEqual(sum(r["outstanding_amount"] for r in past), 3600)
        _, current, _ = execute_report(dict(company=self.company.name, report_date=today(),
            crane=self.crane.name), summary=True)
        self.assertEqual(sum(r["outstanding_amount"] for r in current), 1800)

    def test_migration_preserves_historical_journals_and_snapshots(self):
        from heavy_equipment_rental.patches.shareholder_timesheet_settlements import execute

        sheet = self.sheet()
        self.invoice(sheet).submit()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        before = (settlement.agreement_snapshot, settlement.source_snapshot, settlement.journal_entry,
            self.crane.agreement_history)
        execute()
        execute()
        settlement.reload()
        self.crane.reload()
        self.assertEqual((settlement.agreement_snapshot, settlement.source_snapshot, settlement.journal_entry,
            self.crane.agreement_history), before)

    def test_overlapping_work_period_costs_are_allocated_once(self):
        first = self.sheet(hours=4)
        second = frappe.get_doc(dict(doctype="Crane Timesheet", assignment=self.assignment.name,
            crane=self.crane.name, period_start=self.start, period_end=self.start,
            driver=first.driver, timesheet_entries=[dict(work_date=self.start,
                start_time="13:00", end_time="17:00")])).insert()
        second.submit()
        journal = frappe.get_doc(dict(doctype="Journal Entry", company=self.company.name, posting_date=self.start,
            accounts=[dict(account=self.company.default_expense_account, debit_in_account_currency=1000,
                cost_center=self.company.cost_center, crane=self.crane.name),
                dict(account=self.company.default_cash_account, credit_in_account_currency=1000)])).insert()
        journal.submit()
        self.invoice().submit()
        second.reload()
        settlements = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        self.assertEqual([s.operating_expenses for s in settlements], [500, 500])
        self.assertEqual(sum(s.external_distribution for s in settlements), 3100)
        with self.assertRaises(frappe.ValidationError):
            journal.cancel()

    def test_automation_and_reports_keep_accounting_permissions(self):
        sheet = self.sheet()
        invoice = self.invoice(sheet)
        permission = frappe.permissions.has_permission

        def deny(doctype, *args, **kwargs):
            ptype = kwargs.get("ptype") or (args[0] if args else "read")
            if doctype == "Journal Entry" and ptype in ("create", "submit"):
                if kwargs.get("throw"):
                    raise frappe.PermissionError
                return False
            return permission(doctype, *args, **kwargs)

        frappe.db.savepoint("denied_auto_accrual")
        with patch("frappe.permissions.has_permission", side_effect=deny), self.assertRaises(frappe.PermissionError):
            invoice.submit()
        frappe.db.rollback(save_point="denied_auto_accrual")
        self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "docstatus"), 0)
        self.assertEqual(frappe.db.get_value("Crane Profit Settlement", sheet.profit_settlement, "docstatus"), 0)
        self.invoice(sheet).submit()
        from frappe.model.document import Document
        check = Document.check_permission

        def deny_source(doc, *args, **kwargs):
            if doc.doctype == "Sales Invoice" and doc.name == invoice.name:
                raise frappe.PermissionError
            return check(doc, *args, **kwargs)

        with patch.object(Document, "check_permission", deny_source), self.assertRaises(frappe.PermissionError):
            execute_report(dict(company=self.company.name, report_date=today(), crane=self.crane.name))

    def test_shareholder_selection_supersedes_hidden_supplier_aliases(self):
        supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name="HER legacy alias " + self.key,
            supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"), supplier_type="Company")).insert()
        self.crane.ownership_partners[1].supplier = supplier.name
        self.crane.update(dict(ownership_type="Operated by Partner", operator_type="External Operator",
            operating_partner=supplier.name, operating_shareholder=self.partners[1].name,
            agreement_effective_from=self.start))
        self.crane.save()
        self.assertFalse(self.crane.ownership_partners[1].supplier)
        self.assertFalse(self.crane.operating_partner)
        sheet = self.sheet()
        self.invoice(sheet).submit()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        amounts = {r.shareholder: r.amount for r in settlement.shares if not r.is_company}
        self.assertEqual(amounts, {self.partners[0].name: 1800, self.partners[1].name: 2600})

    def rental_expense(self, amount=900, **values):
        template = frappe.get_doc("Expense Entry", self.cycle["expenses"][0])
        doc = frappe.get_doc(dict(doctype="Expense Entry", company=self.company.name,
            posting_date=today(), crane=self.crane.name, crane_assignment=self.assignment.name,
            description="HER work expense " + self.key, mode_of_payment=template.mode_of_payment,
            expenses=[dict(expense_entry_type=template.expenses[0].expense_entry_type, amount=amount)]))
        doc.update(values)
        return doc

    def test_late_assignment_expense_is_allocated_only_once_by_worked_hours(self):
        first, second = self.sheet(hours=8), self.sheet(offset=1, hours=4)
        expense = self.rental_expense().insert()
        self.assertEqual(str(expense.service_from_date), str(self.start))
        expense.submit()
        self.invoice().submit()
        settlements = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        self.assertEqual([s.operating_expenses for s in settlements], [600, 300])
        for doc in settlements:
            sources = [r for r in json.loads(doc.source_snapshot) if r["name"] == expense.name]
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["rental_assignment"], self.assignment.name)
            self.assertEqual(sources[0]["posting_date"], today())
        with self.assertRaisesRegex(frappe.ValidationError, "closed"):
            self.rental_expense(100).insert().submit()
        with self.assertRaises(frappe.ValidationError):
            self.sheet(offset=2)
        with self.assertRaises(frappe.ValidationError):
            expense.cancel()

    def test_service_dates_and_assignment_isolate_expenses(self):
        first, second = self.sheet(), self.sheet(offset=1)
        expense = self.rental_expense(250, service_from_date=self.start, service_to_date=self.start).insert()
        expense.submit()
        unrelated = self.rental_expense(1000, crane_assignment=self.cycle["assignment"]).insert()
        unrelated.submit()
        self.invoice().submit()
        self.assertEqual(frappe.get_doc("Crane Profit Settlement", first.profit_settlement).operating_expenses, 250)
        self.assertEqual(frappe.get_doc("Crane Profit Settlement", second.profit_settlement).operating_expenses, 0)

    def test_expense_work_terms_validate_and_company_matches(self):
        for values in [dict(service_from_date=self.start),
                       dict(service_from_date=add_days(self.start, 1), service_to_date=self.start),
                       dict(service_from_date=add_days(self.start, -1), service_to_date=self.start),
                       dict(crane=self.crane.name + "-missing")]:
            with self.assertRaises(frappe.ValidationError):
                self.rental_expense(**values).insert()

    def test_period_expense_service_proration(self):
        from heavy_equipment_rental.profit_sharing import collect_sources
        expense = self.rental_expense(100, crane_assignment=None,
            service_from_date=self.start, service_to_date=add_days(self.start, 3)).insert()
        expense.submit()
        totals = []
        for offset in (0, 2):
            sources = collect_sources(self.crane.name, self.company.name,
                add_days(self.start, offset), add_days(self.start, offset + 1))
            totals.append(sum(r.get("expenses", 0) for r in sources if r["name"] == expense.name))
        self.assertEqual(totals, [50, 50])

    def test_period_expense_rounding_and_consecutive_closure(self):
        from heavy_equipment_rental.profit_sharing import collect_sources
        from heavy_equipment_rental.timesheet_settlement import validate_source_allocations
        expense = self.rental_expense(0.01, crane_assignment=None,
            service_from_date=self.start, service_to_date=add_days(self.start, 2)).insert()
        expense.submit()
        parts = []
        for offset in range(3):
            day = add_days(self.start, offset)
            parts.extend(r for r in collect_sources(self.crane.name, self.company.name, day, day)
                if r["name"] == expense.name)
        self.assertEqual([r["expenses"] for r in parts], [0.01, 0, 0])
        # Model a previously closed period without changing its posted ledgers.
        doc = frappe.get_doc(dict(doctype="Crane Profit Settlement", crane=self.crane.name,
            settlement_basis="Period", name="new-period"))
        old = frappe._dict(name="earlier-period", settlement_basis="Period", timesheet=None,
            source_snapshot=json.dumps([parts[0]]))
        with patch("heavy_equipment_rental.timesheet_settlement.frappe.get_all", return_value=[old]):
            validate_source_allocations(doc, [parts[1]])
            with self.assertRaisesRegex(frappe.ValidationError, "already covered"):
                validate_source_allocations(doc, [parts[0]])
