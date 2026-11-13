"""Explicit development examples, real posted documents and numerical evidence.

Never called from installation or migration. A repeated run reads the completed
settlements; it does not pay a partner twice.
"""

import json

import frappe
from frappe.utils import add_days, flt

from heavy_equipment_rental.demo import _create_cycle
from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement import make_partner_payment


PREFIX = "HER OPERATING FIRST DEMO v2 No Tax - "


def create_operating_cycles(company="cranes company", start_date="2026-11-01"):
    frappe.only_for("System Manager")
    result = []
    for case, percentages, ownership, amounts in (
        ("Single Owner", [100], [100], (8000, 2000, 8000, 2000)),
        ("Three Partners", [50, 30, 20], [60, 25, 15], (8000, 2000, 8000, 2000)),
        ("Deficit Rejected", [100], [100], (40000, 1000, 40000, 10000)),
    ):
        location = PREFIX + case
        existing = frappe.db.get_value("Crane Assignment", {"company": company, "location": location}, "name")
        if existing:
            crane = frappe.get_doc("Crane Assignment", existing).assigned_cranes[0].crane
            settlements = frappe.get_all("Crane Profit Settlement", filters={"crane": crane, "docstatus": 1},
                                        pluck="name", order_by="from_date")
            if settlements:
                periods = [describe_settlement(n) for n in settlements]
                for period in periods:
                    _verify_no_tax_period(period)
                result.append(dict(case=case, periods=periods))
                continue
            frappe.throw("An incomplete operating demo exists; review its documents before running again.")
        frappe.db.savepoint("operating_demo_case")
        try:
            cycle = _create_cycle(company, start_date, location=location, daily_rate=100000,
                                  tax_amount=0, expense_amounts=amounts, rental_days=1)
            crane = frappe.get_doc("Crane", cycle["crane"])
            crane.crane_name = location
            settings = frappe.get_doc("Company", company)
            partners = []
            for index, (profit, owned) in enumerate(zip(percentages, ownership), 1):
                supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name=location + f" / Partner {index}",
                    supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
                partners.append(dict(supplier=supplier.name, ownership_percentage=owned, profit_percentage=profit))
            crane.update(dict(ownership_type="Operated for Owner", sharing_company=company,
                agreement_effective_from=cycle["from_date"], operator_type="Our Company", operating_percentage=10,
                profit_allocation_account=settings.default_expense_account,
                partner_payable_account=settings.default_payable_account, sharing_cost_center=settings.cost_center))
            crane.set("ownership_partners", partners)
            crane.save()
            doc = frappe.get_doc(dict(doctype="Crane Profit Settlement", crane=crane.name,
                from_date=cycle["from_date"], to_date=cycle["to_date"], posting_date=cycle["to_date"]))
            if case == "Deficit Rejected":
                # Keep successful examples, but leave no failed-case records.
                # This includes its invoice, receipt, expenses and draft.
                try:
                    doc.insert()
                except frappe.ValidationError as error:
                    message = str(error)
                    if "1,000.00" not in message:
                        raise
                    frappe.db.rollback(save_point="operating_demo_case")
                    result.append(dict(case=case, revenue=100000, operating_fee=10000,
                        balance_after_operating=90000, expenses=91000, shortfall=1000,
                        posted=False, error=message))
                    continue
                raise AssertionError("A deficit settlement was incorrectly accepted")
            doc.insert()
            doc.submit()
            _pay(doc, partial=case == "Single Owner")
            periods = [describe_settlement(doc.name)]
            _verify_no_tax_period(periods[0])
            periods[0].update(customer_receipt=cycle["customer_receipt"], treasury_transfer=cycle["treasury_transfer"])
            if case == "Three Partners":
                old_snapshot = doc.agreement_snapshot
                day = add_days(cycle["to_date"], 1)
                crane.agreement_effective_from = day
                crane.operating_percentage = 12
                for row, profit, owned in zip(crane.ownership_partners, [40, 35, 25], [50, 30, 20]):
                    row.profit_percentage, row.ownership_percentage = profit, owned
                crane.save()
                invoice = frappe.copy_doc(frappe.get_doc("Sales Invoice", cycle["timesheets"][0].sales_invoice))
                invoice.docstatus = 0
                invoice.set_posting_time = 1
                invoice.posting_date = invoice.due_date = day
                invoice.insert()
                invoice.submit()
                from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
                receipt = get_payment_entry("Sales Invoice", invoice.name, bank_account=_cash(company))
                receipt.posting_date, receipt.reference_date = day, day
                receipt.reference_no = "HER operating demo second receipt"
                receipt.insert()
                receipt.submit()
                journal = frappe.get_doc(dict(doctype="Journal Entry", company=company, posting_date=day,
                    accounts=[dict(account=settings.default_expense_account, crane=crane.name,
                        cost_center=settings.cost_center, debit_in_account_currency=20000),
                        dict(account=_cash(company), credit_in_account_currency=20000)])).insert()
                journal.submit()
                second = frappe.get_doc(dict(doctype="Crane Profit Settlement", crane=crane.name,
                    from_date=day, to_date=day, posting_date=day)).insert()
                second.submit()
                _pay(second)
                doc.reload()
                if doc.agreement_snapshot != old_snapshot:
                    raise AssertionError("A changed agreement rewrote historical terms")
                periods.append(describe_settlement(second.name))
                _verify_no_tax_period(periods[-1])
                periods[-1]["customer_receipt"] = receipt.name
            result.append(dict(case=case, periods=periods))
        except Exception:
            frappe.db.rollback(save_point="operating_demo_case")
            raise
    return dict(site=frappe.local.site, company=company, cases=result)


def _verify_no_tax_period(period):
    """Reconcile the user's tax-free example against the posted native ledger."""
    for invoice in period["invoice_headers"]:
        if (invoice.base_net_total != 100000 or invoice.base_grand_total != 100000
                or invoice.base_total_taxes_and_charges
                or frappe.db.count("Sales Taxes and Charges", {"parent": invoice.name,
                    "parenttype": "Sales Invoice"})):
            raise AssertionError("The operating demo must invoice 100,000 with no tax rows")
    ledger = period["ledger_reconciliation"]
    if (ledger["sales_tax_credit"] or ledger["income"] != period["revenue"]
            or ledger["result_after_allocation"] != period["company_retained"]):
        raise AssertionError("Tax-free company retention does not reconcile to the demo ledger")


def _cash(company):
    return frappe.db.get_value("Account", {"company": company, "account_name": "HER Demo Cash"}, "name")


def _pay(doc, partial=False):
    for row in doc.shares:
        if row.is_company or not row.amount:
            continue
        for index, amount in enumerate(([20000, row.amount - 20000] if partial else [row.amount]), 1):
            payment = frappe.get_doc(make_partner_payment(doc.name, row.supplier))
            payment.paid_from = _cash(doc.company)
            payment.paid_amount = payment.received_amount = payment.references[0].allocated_amount = amount
            payment.posting_date = payment.reference_date = doc.posting_date
            payment.reference_no = f"HER operating demo {doc.name} / {index}"
            payment.insert()
            payment.submit()


def describe_settlement(name):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

    doc = frappe.get_doc("Crane Profit Settlement", name)
    source = json.loads(doc.source_snapshot)
    journal = frappe.get_doc("Journal Entry", doc.journal_entry) if doc.journal_entry else None
    shares = []
    for row in doc.shares:
        outstanding = 0
        if not row.is_company and row.amount:
            outstanding = get_reference_details("Journal Entry", doc.journal_entry, doc.currency,
                                                 "Supplier", row.supplier).outstanding_amount
        shares.append(dict(company=bool(row.is_company), supplier=row.supplier, ownership_percentage=row.ownership_percentage,
            residual_percentage=row.profit_percentage, operating_amount=row.operating_amount,
            residual_amount=row.residual_amount, total=row.amount, outstanding=outstanding))
    payments = frappe.get_all("Payment Entry Reference", filters={"reference_doctype": "Journal Entry",
        "reference_name": doc.journal_entry, "docstatus": 1}, fields=["parent", "allocated_amount"])
    conservation = flt(doc.operating_expenses + sum(r.amount for r in doc.shares), 2)
    if conservation != doc.revenue or any(s["outstanding"] for s in shares):
        raise AssertionError("Settlement conservation or partner payment reconciliation failed")
    invoices = []
    for invoice_name in sorted({s["name"] for s in source if s["doctype"] == "Sales Invoice"}):
        invoices.append(frappe.db.get_value("Sales Invoice", invoice_name,
            ["name", "base_net_total", "base_total_taxes_and_charges", "base_grand_total", "outstanding_amount"], as_dict=True))
    vouchers = {s.get("journal") or s["name"] for s in source}
    vouchers.add(doc.journal_entry)
    native_income = native_costs = allocation_expense = tax_credit = 0
    for entry in frappe.get_all("GL Entry", filters={"company": doc.company,
            "voucher_no": ["in", list(filter(None, vouchers))], "is_cancelled": 0},
            fields=["account", "debit", "credit", "voucher_no", "voucher_type"]):
        root, account_type = frappe.get_cached_value("Account", entry.account, ["root_type", "account_type"])
        if root == "Income":
            native_income += entry.credit - entry.debit
        if root == "Expense":
            if entry.voucher_no == doc.journal_entry:
                allocation_expense += entry.debit - entry.credit
            else:
                native_costs += entry.debit - entry.credit
        if account_type == "Tax" and entry.voucher_type == "Sales Invoice":
            tax_credit += entry.credit - entry.debit
    return dict(settlement=doc.name, crane=doc.crane, from_date=str(doc.from_date), to_date=str(doc.to_date),
        currency=doc.currency, revenue=doc.revenue, operating_percentage=doc.operating_percentage,
        operating_fee=doc.operating_fee, balance_after_operating=doc.balance_after_operating,
        expenses=doc.operating_expenses, residual=doc.distributable_profit, company_retained=doc.company_retained,
        partner_payable=doc.external_distribution, journal=doc.journal_entry,
        journal_debit=journal.total_debit if journal else 0, journal_credit=journal.total_credit if journal else 0,
        conservation_total=conservation, shares=shares, payments=payments, sources=source,
        invoice_headers=invoices, ledger_reconciliation=dict(income=native_income, operating_expenses=native_costs,
            allocation_expense=allocation_expense, result_after_allocation=native_income-native_costs-allocation_expense,
            sales_tax_credit=tax_credit))
