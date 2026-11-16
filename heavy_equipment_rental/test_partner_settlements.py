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
        location = frappe.get_doc(dict(doctype="Location", location_name="HER auto " + self.key)).insert().name
        self.assignment = frappe.get_doc(dict(doctype="Rental Contract", company=self.company.name,
            customer=frappe.get_doc("Rental Contract", self.cycle["assignment"]).customer,
            location=location, assigned_cranes=[dict(crane=self.crane.name,
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

    def test_payment_form_reallocates_partial_shareholder_payment(self):
        sheet = self.sheet()
        self.invoice(sheet).submit()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        payment = frappe.get_doc(make_partner_payment(settlement.name, shareholder=self.partners[0].name))
        entitlement = payment.paid_amount
        # Exercise the same server method called after editing Paid Amount in Desk.
        payment.paid_amount = payment.received_amount = 500
        payment.allocate_amount_to_references(500, True, True)
        self.assertEqual(payment.references[0].allocated_amount, 500)
        payment.reference_no, payment.reference_date = "HER form partial", today()
        payment.insert().submit()
        balance = settlement_payment_details(settlement.name)["balances"][0]
        self.assertEqual((balance["paid_amount"], balance["outstanding_amount"], balance["status"]),
            (500, entitlement - 500, "Partly Paid"))

        remaining = frappe.get_doc(make_partner_payment(settlement.name, shareholder=self.partners[0].name))
        for amount in (0, 100, 300, entitlement + 100):
            remaining.allocate_amount_to_references(amount, True, True)
            self.assertEqual(remaining.references[0].allocated_amount, min(amount, entitlement - 500))
        remaining.allocate_amount_to_references(300, True, False)
        self.assertEqual(remaining.references[0].allocated_amount, 0)
        remaining.allocate_amount_to_references(remaining.paid_amount, False, True)
        remaining.reference_no, remaining.reference_date = "HER form remainder", today()
        remaining.insert().submit()
        self.assertEqual(settlement_payment_details(settlement.name)["balances"][0]["status"], "Paid")
        remaining.cancel()
        payment.cancel()
        self.assertEqual(settlement_payment_details(settlement.name)["balances"][0]["outstanding_amount"], entitlement)

    def test_payment_allocator_keeps_native_non_settlement_behavior(self):
        from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry

        payment = frappe.new_doc("Payment Entry")
        for party_type, settlement in (("Supplier", "CPS-test"), ("Customer", None), ("Shareholder", None)):
            payment.party_type, payment.crane_profit_settlement = party_type, settlement
            payment.payment_type = "Pay"
            with patch.object(PaymentEntry, "allocate_amount_to_references") as native:
                payment.allocate_amount_to_references(100, True, True)
                native.assert_called_once_with(100, True, True)

    def test_combined_partner_payment_from_open_entitlements(self):
        from heavy_equipment_rental.partner_payment import get_open_partner_entitlements

        first, second = self.sheet(), self.sheet(offset=1, hours=4)
        self.invoice(first).submit()
        self.invoice(second).submit()
        a, b = [frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement) for sheet in (first, second)]
        payment = frappe.get_doc(make_partner_payment(a.name, shareholder=self.partners[0].name))
        args = dict(company=self.company.name, party_type="Shareholder", party=self.partners[0].name,
            paid_to=payment.paid_to)
        rows = get_open_partner_entitlements(**args)
        self.assertEqual([r["settlement"] for r in rows], [a.name, b.name])
        self.assertEqual([r["outstanding_amount"] for r in rows], [1800, 900])
        for field, value in (("timesheet", second.name), ("sales_invoice", b.sales_invoice)):
            self.assertEqual([r["settlement"] for r in get_open_partner_entitlements(**args, **{field: value})], [b.name])
        self.assertEqual(get_open_partner_entitlements(**args, to_date="2000-01-01"), [])
        self.assertEqual(get_open_partner_entitlements(**args, crane="missing crane"), [])
        payment.set("references", [dict(reference_doctype=r["reference_doctype"], reference_name=r["reference_name"],
            total_amount=r["total_amount"], outstanding_amount=r["outstanding_amount"], exchange_rate=r["exchange_rate"])
            for r in rows])
        payment.paid_amount = payment.received_amount = 2000
        payment.allocate_amount_to_references(2000, True, True)
        self.assertEqual([r.allocated_amount for r in payment.references], [1800, 200])
        payment.reference_no, payment.reference_date = "HER combined", today()
        payment.insert().submit()
        self.assertFalse(payment.crane_profit_settlement or payment.crane_timesheet or payment.crane)
        self.assertEqual(settlement_payment_details(a.name)["balances"][0]["status"], "Paid")
        self.assertEqual(settlement_payment_details(b.name)["balances"][0]["status"], "Partly Paid")
        self.assertEqual([r["amount"] for r in settlement_payment_details(b.name)["payments"]], [200])
        remaining = get_open_partner_entitlements(**args)
        self.assertEqual([(r["settlement"], r["outstanding_amount"]) for r in remaining], [(b.name, 700)])
        other = get_open_partner_entitlements(**{**args, "party": self.partners[1].name})
        self.assertEqual([r["outstanding_amount"] for r in other], [1800, 900])
        payment.cancel()
        self.assertEqual([r["outstanding_amount"] for r in get_open_partner_entitlements(**args)], [1800, 900])

    def test_open_entitlements_permissions_and_account_scope(self):
        from heavy_equipment_rental.partner_payment import get_open_partner_entitlements
        from frappe.model.document import Document

        sheet = self.sheet()
        self.invoice(sheet).submit()
        payment = frappe.get_doc(make_partner_payment(sheet.profit_settlement, shareholder=self.partners[0].name))
        args = dict(company=self.company.name, party_type="Shareholder", party=self.partners[0].name,
            paid_to=payment.paid_to)
        with self.assertRaises(frappe.ValidationError):
            get_open_partner_entitlements(**{**args, "paid_to": self.company.default_cash_account})
        with self.assertRaises(frappe.ValidationError):
            get_open_partner_entitlements(**args, from_date="2026-11-15", to_date="2026-11-14")
        check = Document.check_permission
        def deny_invoice(doc, *a, **kw):
            if doc.doctype == "Sales Invoice":
                raise frappe.PermissionError
            return check(doc, *a, **kw)
        with patch.object(Document, "check_permission", deny_invoice), self.assertRaises(frappe.PermissionError):
            get_open_partner_entitlements(**args)
        user = frappe.session.user
        try:
            frappe.set_user("Guest")
            with self.assertRaises(frappe.PermissionError):
                get_open_partner_entitlements(**args)
        finally:
            frappe.set_user(user)

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
        agreement = json.loads(settlement.agreement_snapshot)
        self.assertEqual((agreement["distribution_posting"], agreement["settlement_approval"],
            agreement["settlement_revenue_basis"], agreement["include_depreciation"]),
            ("Source Revenue Accounts", "On Invoice Submission", "Invoice Grand Total", 0))
        self.assertTrue(all(frappe.get_cached_value("Account", row.account, "root_type") == "Income"
            for row in journal.accounts if row.debit_in_account_currency))
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

    def test_unlinked_expense_is_excluded_and_does_not_close_unrelated_work(self):
        from heavy_equipment_rental.rental_expenses import affected_settlements
        first = self.sheet()
        expense = self.rental_expense(700, crane_assignment=None,
            posting_date=self.start).insert()
        expense.submit()
        self.invoice(first).submit()
        settlement = frappe.get_doc("Crane Profit Settlement", first.profit_settlement)
        self.assertEqual(settlement.operating_expenses, 0)
        self.assertEqual(affected_settlements(expense), [])
        snapshot = settlement.source_snapshot
        # Legacy snapshots remain protected even when their source has no links.
        legacy_sources = json.loads(snapshot) + [dict(doctype="Expense Entry", name=expense.name, expenses=700)]
        frappe.db.set_value("Crane Profit Settlement", settlement.name, "source_snapshot", json.dumps(legacy_sources))
        self.assertEqual(affected_settlements(expense), [settlement.name])
        from heavy_equipment_rental.profit_sharing import guard_closed_period
        with self.assertRaisesRegex(frappe.ValidationError, "included in settlement"):
            guard_closed_period(expense, "before_cancel")
        with self.assertRaisesRegex(frappe.ValidationError, "included in settlement"):
            guard_closed_period(frappe.get_doc("Journal Entry", expense.journal_entry), "before_cancel")
        frappe.db.set_value("Crane Profit Settlement", settlement.name, "source_snapshot", snapshot)
        # An unallocated cost may be posted/cancelled even on a closed work date.
        self.rental_expense(100, crane_assignment=None, posting_date=self.start).insert().submit()
        expense.cancel()
        self.assertEqual(settlement.reload().source_snapshot, snapshot)

    def test_assignment_expense_ignores_service_date_for_timesheet_allocation(self):
        first, second = self.sheet(hours=8), self.sheet(offset=1, hours=4)
        expense = self.rental_expense(900, service_from_date=self.start,
            service_to_date=self.start).insert()
        expense.submit()
        self.invoice().submit()
        settlements = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        self.assertEqual([s.operating_expenses for s in settlements], [600, 300])
        # A late cost for the same assignment cannot evade its existing closure.
        with self.assertRaisesRegex(frappe.ValidationError, "closed"):
            self.rental_expense(10, service_from_date=add_days(self.start, 3),
                service_to_date=add_days(self.start, 3)).insert().submit()
        with self.assertRaisesRegex(frappe.ValidationError, "same rental job"):
            self.rental_expense(crane_timesheet=first.name,
                crane_assignment=self.cycle["assignment"]).insert()

    def test_native_repair_costs_use_explicit_links_only(self):
        from heavy_equipment_rental.crane_repairs import make_repair_document, validate_repair_closure
        first, second = self.sheet(hours=8), self.sheet(offset=1, hours=4)
        supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name="HER repair " + self.key,
            supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
        for amount, links in [(700, {}), (900, dict(crane_assignment=self.assignment.name)),
                              (250, dict(crane_timesheet=first.name))]:
            # Repairs can be paid/performed after the work they explicitly charge.
            job = frappe.get_doc(dict(doctype="Crane Maintenance", crane=self.crane.name,
                company=self.company.name, cost_treatment="Operating Expense", maintenance_type="Corrective",
                actual_start_date=today(), actual_end_date=today(), description="Explicit allocation", **links)).insert()
            invoice = frappe.get_doc(make_repair_document(job.name, "Purchase Invoice"))
            invoice.supplier = supplier.name
            invoice.append("items", dict(item_code=self.crane.item, qty=1, rate=amount,
                expense_account=self.company.default_expense_account, cost_center=self.company.cost_center))
            invoice.insert().submit()
            job.submit()
        pending = frappe.get_doc(dict(doctype="Crane Maintenance", crane=self.crane.name,
            company=self.company.name, cost_treatment="Operating Expense", maintenance_type="Corrective",
            actual_start_date=self.start, actual_end_date=self.start, description="Unallocated pending repair")).insert()
        self.invoice().submit()
        settlements = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        self.assertEqual([s.operating_expenses for s in settlements], [850, 300])
        validate_repair_closure(settlements[0])  # Unallocated pending repair is irrelevant.
        pending.crane_assignment = self.assignment.name
        pending.save()
        with self.assertRaisesRegex(frappe.ValidationError, "Complete or cancel repair"):
            validate_repair_closure(settlements[0])

    def test_late_assignment_expense_is_allocated_only_once_by_worked_hours(self):
        expense = self.rental_expense().insert()
        self.assertEqual(str(expense.service_from_date), str(self.start))
        expense.submit()
        first, second = self.sheet(hours=8), self.sheet(offset=1, hours=4)
        self.invoice().submit()
        settlements = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        self.assertEqual([s.operating_expenses for s in settlements], [600, 300])
        for doc in settlements:
            sources = [r for r in json.loads(doc.source_snapshot) if r["name"] == expense.name]
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["rental_assignment"], self.assignment.name)
            self.assertEqual(sources[0]["posting_date"], today())
        with self.assertRaisesRegex(frappe.ValidationError, "closed"):
            self.rental_expense(100, crane_timesheet=first.name).insert().submit()
        with self.assertRaises(frappe.ValidationError):
            self.sheet(offset=2)
        with self.assertRaises(frappe.ValidationError):
            expense.cancel()

    def test_service_dates_and_assignment_isolate_expenses(self):
        first, second = self.sheet(), self.sheet(offset=1)
        expense = self.rental_expense(250, crane_timesheet=first.name, service_from_date=self.start, service_to_date=self.start).insert()
        expense.submit()
        unrelated = self.rental_expense(1000, crane_assignment=self.cycle["assignment"], crane_timesheet=self.cycle["timesheets"][0].name).insert()
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
        expense = self.rental_expense(100,
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
        expense = self.rental_expense(0.01,
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

    def test_rental_context_requires_selection_and_timesheet_cost_is_direct(self):
        from heavy_equipment_rental.rental_context import rental_work_options
        first, second = self.sheet(), self.sheet(offset=1)
        options = rental_work_options(self.crane.name, self.start, self.start, self.company.name)
        self.assertIn(self.assignment.name, [r['name'] for r in options['assignments']])
        self.assertIn(first.name, [r['name'] for r in options['timesheets']])
        self.assertNotIn(second.name, [r['name'] for r in options['timesheets']])
        optional = self.rental_expense().insert()
        self.assertFalse(optional.crane_timesheet)
        standalone = self.rental_expense(50, crane_assignment=None, posting_date=add_days(self.start, 10)).insert()
        standalone.submit()
        self.assertFalse(standalone.crane_assignment)
        self.assertFalse(standalone.crane_timesheet)
        crane_only = self.rental_expense(crane_assignment=None, posting_date=self.start).insert()
        self.assertFalse(crane_only.crane_assignment)
        self.assertFalse(crane_only.crane_timesheet)
        expense = self.rental_expense(250, crane_assignment=None, crane_timesheet=first.name).insert()
        self.assertEqual(expense.crane_assignment, self.assignment.name)
        expense.submit()
        self.invoice().submit()
        self.assertEqual(frappe.get_doc('Crane Profit Settlement', first.profit_settlement).operating_expenses,250)
        self.assertEqual(frappe.get_doc('Crane Profit Settlement', second.profit_settlement).operating_expenses,0)

    def test_maintenance_rental_context_carries_to_expense(self):
        first = self.sheet()
        template = self.rental_expense()
        crane_only = frappe.get_doc(dict(doctype='Crane Maintenance', cost_treatment='Cash Expense', crane=self.crane.name,
            maintenance_type='Corrective', description='Optional rental selection',
            actual_start_date=self.start, actual_end_date=self.start)).insert()
        self.assertFalse(crane_only.crane_assignment)
        self.assertFalse(crane_only.crane_timesheet)
        maintenance = frappe.get_doc(dict(doctype='Crane Maintenance', cost_treatment='Cash Expense', crane=self.crane.name,
            crane_timesheet=first.name, maintenance_type='Corrective', description='Selected rental maintenance',
            actual_start_date=self.start, actual_end_date=self.start,
            expense_type=template.expenses[0].expense_entry_type, mode_of_payment=template.mode_of_payment,
            cost=100)).insert()
        self.assertEqual(maintenance.crane_assignment,self.assignment.name)
        maintenance.submit()
        expense=frappe.get_doc('Expense Entry',maintenance.expense_entry)
        self.assertEqual((expense.crane_assignment,expense.crane_timesheet,expense.docstatus),
            (self.assignment.name,first.name,1))
        self.assertEqual(str(expense.service_from_date), str(self.start))
        self.assertEqual(str(expense.service_to_date), str(self.start))
        with self.assertRaisesRegex(frappe.ValidationError,'Expense details cannot change|Not allowed to change'):
            maintenance.crane_timesheet=None
            maintenance.save()


    def test_restore_migration_is_dated_idempotent_and_preserves_posted_snapshots(self):
        from heavy_equipment_rental.patches.restore_automatic_revenue_settlements import execute, RESTORED_TERMS
        sheet = self.sheet()
        self.invoice(sheet).submit()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        snapshot = settlement.agreement_snapshot
        journal = frappe.get_doc("Journal Entry", settlement.journal_entry).as_dict()
        self.crane.update(dict(agreement_effective_from=add_days(self.start, 1),
            settlement_approval="Review Before Posting", distribution_posting="Partner Expense",
            profit_allocation_account=self.company.default_expense_account,
            settlement_revenue_basis="Net Revenue", include_depreciation=1))
        self.crane.save()
        previous = json.loads(self.crane.agreement_history)
        counts = {dt: frappe.db.count(dt) for dt in ("GL Entry", "Payment Entry", "Journal Entry", "Crane Profit Settlement")}
        execute()
        self.crane.reload()
        restored = json.loads(self.crane.agreement_history)
        self.assertEqual(restored[:-1], previous)
        self.assertGreater(restored[-1]["effective_from"], previous[-1]["effective_from"])
        self.assertGreater(restored[-1]["effective_from"], str(settlement.to_date))
        self.assertTrue(all(self.crane.get(k) == v for k, v in RESTORED_TERMS.items()))
        execute()
        self.assertEqual(json.loads(self.crane.reload().agreement_history), restored)
        self.assertEqual(settlement.reload().agreement_snapshot, snapshot)
        self.assertEqual(frappe.get_doc("Journal Entry", settlement.journal_entry).as_dict(), journal)
        self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})

    def test_confirmed_cancel_all_from_invoice_and_timesheet(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all

        for root in ("Sales Invoice", "Crane Timesheet"):
            sheet = self.sheet(offset=0 if root == "Sales Invoice" else 1)
            invoice = self.invoice(sheet)
            invoice.submit()
            settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
            name = invoice.name if root == "Sales Invoice" else sheet.name
            plan = get_plan(root, name)
            keys = [(row["doctype"], row["name"]) for row in plan]
            self.assertEqual(len(keys), len(set(keys)))
            with self.assertRaises(frappe.ValidationError):
                cancel_all(root, name, "[]")
            self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "docstatus"), 1)
            # A downstream accounting failure must restore already cancelled entitlements.
            invoice_class = type(invoice)
            with patch.object(invoice_class, "cancel", side_effect=frappe.ValidationError("Cancellation blocked")):
                with self.assertRaises(frappe.ValidationError):
                    cancel_all(root, name, frappe.as_json(plan))
            for row in plan:
                self.assertEqual(frappe.db.get_value(row["doctype"], row["name"], "docstatus"), 1)
            cancel_all(root, name, frappe.as_json(plan))
            for dt, dn in (("Sales Invoice", invoice.name), ("Crane Timesheet", sheet.name),
                           ("Crane Profit Settlement", settlement.name),
                           ("Journal Entry", settlement.journal_entry)):
                self.assertEqual(frappe.db.get_value(dt, dn, "docstatus"),
                                 1 if dt == "Crane Timesheet" and root == "Sales Invoice" else 2)

    def test_cancel_settlement_preserves_invoice_and_work(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all

        sheet = self.sheet()
        invoice = self.invoice(sheet)
        invoice.submit()
        settlement = frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)
        plan = get_plan(settlement.doctype, settlement.name)
        self.assertEqual({r["doctype"] for r in plan}, {"Crane Profit Settlement", "Journal Entry"})
        cancel_all(settlement.doctype, settlement.name, frappe.as_json(plan))
        self.assertEqual(sheet.reload().docstatus, 1)
        self.assertEqual(invoice.reload().docstatus, 1)
        self.assertEqual(settlement.reload().docstatus, 2)
        self.assertEqual(frappe.db.get_value("Journal Entry", settlement.journal_entry, "docstatus"), 2)

    def correction_cycle(self):
        sheet = self.sheet()
        expense = self.rental_expense(crane_timesheet=sheet.name,
            service_from_date=sheet.period_start, service_to_date=sheet.period_end).insert()
        expense.submit()
        invoice = self.invoice(sheet)
        invoice.submit()
        return sheet, expense, invoice, frappe.get_doc("Crane Profit Settlement", sheet.profit_settlement)

    def test_cancel_expense_includes_payments_and_native_amendments(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all
        sheet, expense, invoice, settlement = self.correction_cycle()
        payment = self.pay(settlement, amount=500)
        plan = get_plan(expense.doctype, expense.name)
        self.assertIn(dict(doctype="Payment Entry", name=payment.name), plan)
        cancel_all(expense.doctype, expense.name, plan)
        self.assertTrue(all(d.reload().docstatus == 2 for d in (expense, settlement, payment)))
        self.assertEqual(invoice.reload().docstatus, 1)
        self.assertEqual(sheet.reload().docstatus, 1)
        amended = frappe.copy_doc(expense)
        amended.docstatus = 0
        amended.amended_from = expense.name
        amended.expenses[0].amount = 2000
        amended.insert().submit()
        replacement = frappe.copy_doc(settlement)
        replacement.docstatus = 0
        replacement.amended_from = settlement.name
        replacement.insert().submit()
        self.assertEqual(replacement.operating_expenses, 2000)
        self.assertEqual(replacement.external_distribution, 2600)
        self.assertEqual(sheet.reload().profit_settlement, replacement.name)

    def test_cancel_scope_changes_and_permission_denial(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all
        from frappe.model.document import Document
        sheet, expense, invoice, settlement = self.correction_cycle()
        original = get_plan(expense.doctype, expense.name)
        payment = self.pay(settlement, amount=500)
        with self.assertRaisesRegex(frappe.ValidationError, "Linked documents changed"):
            cancel_all(expense.doctype, expense.name, original)
        plan = get_plan(expense.doctype, expense.name)
        check = Document.check_permission
        def deny(doc, permtype="read", *args, **kwargs):
            if doc.doctype == "Payment Entry" and permtype == "cancel":
                raise frappe.PermissionError
            return check(doc, permtype, *args, **kwargs)
        with patch.object(Document, "check_permission", deny), self.assertRaises(frappe.PermissionError):
            cancel_all(expense.doctype, expense.name, plan)
        with patch.object(type(expense), "cancel", side_effect=frappe.ValidationError("Test failure")):
            with self.assertRaisesRegex(frappe.ValidationError, "Test failure"):
                cancel_all(expense.doctype, expense.name, plan)
        self.assertTrue(all(d.reload().docstatus == 1 for d in (payment, expense, settlement, invoice)))

    def test_cancel_shared_expense_cancels_all_affected_settlements(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all
        expense = self.rental_expense().insert()
        expense.submit()
        first, second = self.sheet(), self.sheet(offset=1)
        self.invoice().submit()
        plan = get_plan(expense.doctype, expense.name)
        names = {r["name"] for r in plan if r["doctype"] == "Crane Profit Settlement"}
        self.assertEqual(names, {first.profit_settlement, second.profit_settlement})
        cancel_all(expense.doctype, expense.name, plan)
        self.assertTrue(all(frappe.get_doc("Crane Profit Settlement", n).docstatus == 2 for n in names))

    def test_cancel_combined_partner_payment_keeps_other_settlement(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all
        first, second = self.sheet(), self.sheet(offset=1)
        self.invoice(first).submit()
        self.invoice(second).submit()
        a, b = [frappe.get_doc("Crane Profit Settlement", s.profit_settlement) for s in (first, second)]
        payment = frappe.get_doc(make_partner_payment(a.name, shareholder=self.partners[0].name))
        other = frappe.get_doc(make_partner_payment(b.name, shareholder=self.partners[0].name))
        payment.append("references", other.references[0].as_dict())
        payment.paid_amount = payment.received_amount = 3600
        payment.allocate_amount_to_references(3600, True, True)
        payment.reference_no, payment.reference_date = "Combined cancellation", today()
        payment.insert().submit()
        plan = get_plan(a.doctype, a.name)
        self.assertEqual(sum(r["doctype"] == "Payment Entry" for r in plan), 1)
        self.assertNotIn(dict(doctype=b.doctype, name=b.name), plan)
        cancel_all(a.doctype, a.name, plan)
        self.assertEqual(payment.reload().docstatus, 2)
        self.assertEqual(b.reload().docstatus, 1)
        self.assertEqual(settlement_payment_details(b.name)["balances"][0]["outstanding_amount"], 1800)

    def test_cancel_invoice_includes_customer_receipt(self):
        from heavy_equipment_rental.cancellation import get_plan, cancel_all
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
        sheet, expense, invoice, settlement = self.correction_cycle()
        receipt = get_payment_entry("Sales Invoice", invoice.name,
            bank_account=self.company.default_cash_account)
        receipt.reference_no, receipt.reference_date = "Cancel receipt test", today()
        receipt.insert().submit()
        plan = get_plan(invoice.doctype, invoice.name)
        self.assertIn(dict(doctype="Payment Entry", name=receipt.name), plan)
        cancel_all(invoice.doctype, invoice.name, plan)
        self.assertEqual(receipt.reload().docstatus, 2)
        self.assertEqual(invoice.reload().docstatus, 2)
        self.assertEqual(settlement.reload().docstatus, 2)
        self.assertEqual(sheet.reload().docstatus, 1)
        self.assertEqual(expense.reload().docstatus, 1)
