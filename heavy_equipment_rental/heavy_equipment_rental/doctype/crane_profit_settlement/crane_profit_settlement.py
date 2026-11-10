"""Operating share first, costs second, then residual partner distributions."""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.profit_sharing import (
    OPERATING_FIRST, LEGACY_NET, agreement_for, allocate_amount, collect_sources,
    dumps, last_settlement, next_period_start, revenue_allocation_rows, validate_account,
)
from heavy_equipment_rental.rental_validation import lock_cranes
from heavy_equipment_rental.partner_accounts import modern_agreement, share_party


class CraneProfitSettlement(Document):
    def validate(self):
        sheet = None
        if self.timesheet and (self.settlement_basis == "Timesheet" or (self.is_new() and not self.amended_from)):
            self.settlement_basis = "Timesheet"
            sheet = frappe.get_doc("Crane Timesheet", self.timesheet)
            sheet.check_permission("read")
            if sheet.docstatus != 1:
                frappe.throw(_("Select a submitted Crane Timesheet."))
            self.crane = sheet.crane
            self.from_date, self.to_date = sheet.period_start, sheet.period_end
            self.sales_invoice = sheet.sales_invoice
        lock_cranes([self.crane])
        crane = frappe.get_doc("Crane", self.crane)
        crane.check_permission("read")
        if not self.from_date or not self.to_date or getdate(self.from_date) > getdate(self.to_date):
            frappe.throw(_("Enter a valid settlement date range."))
        if getdate(self.to_date) > getdate(today()) and self.docstatus == 1:
            frappe.throw(_("Settle completed periods only."))
        if not self.posting_date or getdate(self.posting_date) < getdate(self.to_date):
            frappe.throw(_("Posting Date must be on or after the period end."))
        agreement = modern_agreement(agreement_for(crane, self.from_date, self.to_date))
        self.company, self.currency = agreement["company"], agreement["currency"]
        frappe.get_doc("Company", self.company).check_permission("read")
        previous = last_settlement(self.crane) if not sheet else None
        if sheet:
            historical = last_settlement(self.crane)
            if historical and historical.loss_carried_forward:
                frappe.throw(_("Resolve the historical carried loss with a period settlement before using automatic Timesheet settlements."))
            duplicate = frappe.db.get_value("Crane Profit Settlement", {"timesheet": sheet.name,
                "docstatus": ["!=", 2], "name": ["!=", self.name or ""]}, "name")
            if duplicate:
                frappe.throw(_("Timesheet already has settlement {0}.").format(duplicate))
            historical = sheet.profit_settlement
            if historical and historical != self.name and frappe.db.get_value("Crane Profit Settlement", historical, "docstatus") == 1:
                frappe.throw(_("Timesheet is already covered by settlement {0}.").format(historical))
            closed = frappe.db.get_value("Crane Profit Settlement", {"crane": self.crane, "docstatus": 1,
                "settlement_basis": ["!=", "Timesheet"], "from_date": ["<=", self.to_date],
                "to_date": [">=", self.from_date]}, "name")
            if closed:
                frappe.throw(_("Timesheet is covered by period settlement {0}.").format(closed))
        else:
            expected = next_period_start(crane, previous)
            if getdate(self.from_date) != getdate(expected):
                frappe.throw(_("Settle consecutive periods without overlaps or gaps. Next From Date is {0}.").format(expected))
        if self.journal_entry:
            frappe.throw(_("The Journal Entry is assigned automatically on submission."))
        self.calculation_method = agreement.get("calculation_method", LEGACY_NET)
        operating_first = self.calculation_method == OPERATING_FIRST
        if sheet:
            from heavy_equipment_rental.timesheet_settlement import collect_timesheet_sources
            sources = collect_timesheet_sources(sheet, self.company, operating_first)
            if self.docstatus == 1 and (not self.sales_invoice or
                    frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus") != 1):
                frappe.throw(_("Submit the linked Sales Invoice before posting partner entitlements."))
        else:
            sources = collect_sources(self.crane, self.company, self.from_date, self.to_date,
                                      grand_total=operating_first)
        from heavy_equipment_rental.timesheet_settlement import validate_source_allocations
        validate_source_allocations(self, sources)
        precision = self.precision("net_profit")
        self.revenue = flt(sum(r.get("revenue", 0) for r in sources), precision)
        self.operating_expenses = flt(sum(r.get("expenses", 0) for r in sources), precision)
        self.operating_percentage = agreement.get("operating_percentage", 0) if operating_first else 0
        self.operating_fee = flt(self.revenue * self.operating_percentage / 100, precision)
        self.balance_after_operating = flt(self.revenue - self.operating_fee, precision)
        self.net_profit = flt(self.balance_after_operating - self.operating_expenses, precision)
        self.loss_brought_forward = flt(previous.loss_carried_forward if previous else 0, precision)
        available = flt(self.net_profit - self.loss_brought_forward, precision)
        if self.revenue < 0:
            frappe.throw(_("Cannot settle negative revenue: {0} {1}. Review returns and source adjustments.").format(
                f"{self.revenue:,.{precision}f}", self.currency))
        if available < 0:
            frappe.throw(_("Settlement stopped: revenue {0}, operating share {1}, balance after operating {2}, "
                           "expenses {3}, historical loss {4}, shortfall {5} {6}. "
                           "Expenses and historical losses exceed the balance after the operating share. "
                           "No settlement or partner payable was posted.").format(
                *[f"{v:,.{precision}f}" for v in (self.revenue, self.operating_fee,
                    self.balance_after_operating, self.operating_expenses, self.loss_brought_forward, -available)],
                self.currency))
        self.distributable_profit = available
        self.loss_carried_forward = 0
        self.set("shares", [])
        amounts = allocate_amount(self.distributable_profit,
                                  [p["profit_percentage"] for p in agreement["partners"]], precision)
        for partner, amount in zip(agreement["partners"], amounts):
            self.append("shares", dict(partner, residual_amount=amount, operating_amount=0,
                                       amount=amount, currency=self.currency, ledger_party_type="Shareholder"))
        if self.operating_fee:
            operator = next((r for r in self.shares if
                (r.is_company if agreement["operator_type"] == "Our Company" else
                 not r.is_company and r.shareholder == agreement.get("operating_shareholder"))), None)
            if not operator:
                operator = self.append("shares", dict(is_company=1, ownership_percentage=0,
                    profit_percentage=0, residual_amount=0, currency=self.currency))
            operator.operating_amount = self.operating_fee
            operator.amount = flt(operator.residual_amount + operator.operating_amount, precision)
        self.company_retained = flt(sum(r.amount for r in self.shares if r.is_company), precision)
        self.external_distribution = flt(sum(r.amount for r in self.shares if not r.is_company), precision)
        self.agreement_snapshot = dumps(dict(agreement, posting_basis="Source Revenue Accounts")
                                        if operating_first else agreement)
        self.source_snapshot = dumps(sources)

    def on_submit(self):
        if not self.external_distribution:
            return
        agreement = json.loads(self.agreement_snapshot)
        validate_account(agreement["payable_account"], self.company, self.currency, payable=True)
        if self.calculation_method == OPERATING_FIRST:
            debit_rows = revenue_allocation_rows(json.loads(self.source_snapshot),
                self.external_distribution, self.company, self.currency,
                agreement["cost_center"], self.precision("net_profit"))
        else:
            validate_account(agreement["allocation_account"], self.company, self.currency)
            debit_rows = [dict(account=agreement["allocation_account"],
                               debit_in_account_currency=self.external_distribution,
                               cost_center=agreement["cost_center"])]
        journal = frappe.get_doc(dict(
            doctype="Journal Entry", voucher_type="Journal Entry", company=self.company,
            posting_date=self.posting_date,
            user_remark=_("Crane Profit Settlement {0}: {1}, {2} to {3}").format(
                self.name, self.crane, self.from_date, self.to_date),
            accounts=debit_rows + [
                dict(account=agreement["payable_account"], party_type=share_party(r)[0], party=share_party(r)[1],
                     credit_in_account_currency=r.amount)
                for r in self.shares if not r.is_company and r.amount > 0
            ],
        ))
        journal.insert()
        # Register the controlled journal before posting. Source dimensions can
        # include Crane; this posting closes its own period rather than adding
        # new operational revenue or costs to an already closed period.
        self.db_set("journal_entry", journal.name, update_modified=False)
        # Journal Entry.submit queues large journals (>100 rows). Post in this
        # transaction so period closure and its ledger entry remain atomic.
        journal._submit()

    def before_cancel(self):
        lock_cranes([self.crane])
        latest = last_settlement(self.crane) if self.settlement_basis != "Timesheet" else None
        if latest and latest.name != self.name:
            frappe.throw(_("Cancel later settlements first to preserve consecutive periods."))
        if self.journal_entry:
            # ERPNext's optional auto-unlink setting must not leave paid
            # distributions as advances and permit a second distribution.
            frappe.get_doc("Journal Entry", self.journal_entry, for_update=True)
            if frappe.db.exists("Payment Ledger Entry", {
                "against_voucher_type": "Journal Entry", "against_voucher_no": self.journal_entry,
                "voucher_no": ["!=", self.journal_entry], "delinked": 0,
            }):
                frappe.throw(_("Cancel or unreconcile payments against this settlement before cancelling it."))

    def on_cancel(self):
        if not self.journal_entry:
            return
        journal = frappe.get_doc("Journal Entry", self.journal_entry, for_update=True)
        journal.ignore_linked_doctypes = ("Crane Profit Settlement",)
        journal._cancel()


@frappe.whitelist()
def make_partner_payment(settlement, supplier=None, shareholder=None):
    """Return an unsaved native Payment Entry against the supplier's journal balance."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

    frappe.has_permission("Payment Entry", "create", throw=True)
    doc = frappe.get_doc("Crane Profit Settlement", settlement)
    doc.check_permission("read")
    if doc.docstatus != 1 or not doc.journal_entry:
        frappe.throw(_("Select a submitted settlement with a partner payable."))
    partner = next((r for r in doc.shares if not r.is_company and r.amount > 0 and (
        (shareholder and r.shareholder == shareholder) or (supplier and r.supplier == supplier))), None)
    if not partner:
        frappe.throw(_("This Supplier has no distribution in this settlement."))
    party_type, party = share_party(partner)
    frappe.get_doc(party_type, party).check_permission("read")
    details = get_reference_details("Journal Entry", doc.journal_entry, doc.currency, party_type, party)
    outstanding = flt(details.outstanding_amount)
    if outstanding <= 0:
        frappe.throw(_("This partner distribution is already paid."))
    company = frappe.get_doc("Company", doc.company)
    bank = company.default_bank_account or company.default_cash_account
    if bank and frappe.get_cached_value("Account", bank, "account_currency") != doc.currency:
        bank = None
    agreement = json.loads(doc.agreement_snapshot)
    payment = frappe.new_doc("Payment Entry")
    payment.update(dict(payment_type="Pay", company=doc.company, posting_date=today(),
        party_type=party_type, party=party, paid_from=bank, paid_to=agreement["payable_account"],
        crane_profit_settlement=doc.name, crane_timesheet=doc.timesheet, crane=doc.crane,
        paid_from_account_currency=doc.currency, paid_to_account_currency=doc.currency,
        paid_amount=outstanding, received_amount=outstanding, source_exchange_rate=1, target_exchange_rate=1))
    payment.append("references", dict(reference_doctype="Journal Entry", reference_name=doc.journal_entry,
        total_amount=details.total_amount, outstanding_amount=outstanding,
        allocated_amount=outstanding, exchange_rate=1))
    payment.setup_party_account_field()
    payment.set_missing_values()
    return payment.as_dict()
