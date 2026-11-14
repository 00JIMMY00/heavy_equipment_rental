"""Explicit, repeatable development example on an existing Crane; never a hook."""

import json

import frappe
from frappe.utils import add_days, flt, getdate, strip_html, today

from heavy_equipment_rental.billing import generate_sales_invoice
from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement import make_partner_payment
from heavy_equipment_rental.partner_reporting import settlement_payment_details
from heavy_equipment_rental.patches.restore_automatic_revenue_settlements import RESTORED_TERMS

CRANE = "CR-00073"
MARKER = "HER_RESTORED_SETTLEMENT_RESULT="


def run(commit=False):
	frappe.only_for("System Manager")
	if frappe.local.site != "cranes-dev2.arab-erp.com":
		frappe.throw("This explicit example is restricted to the development site.")
	for content in frappe.get_all("Comment", filters={"reference_doctype": "Crane", "reference_name": CRANE}, pluck="content"):
		text = strip_html(content)
		if text.startswith(MARKER):
			return verify(json.loads(text[len(MARKER):]))
	try:
		from heavy_equipment_rental.rental_items import preserve_rental_income_defaults
		with preserve_rental_income_defaults():
			result = verify(create())
		if commit:
			frappe.get_doc("Crane", CRANE).add_comment("Info", MARKER + json.dumps(result, ensure_ascii=False, default=str))
			frappe.db.commit()
		else:
			frappe.db.rollback()
		return result
	except Exception:
		frappe.db.rollback()
		raise


def cash_balance(account):
	return flt(sum(flt(r.debit) - flt(r.credit) for r in frappe.get_all("GL Entry",
		filters={"account": account, "is_cancelled": 0}, fields=["debit", "credit"])), 2)


def create():
	crane = frappe.get_doc("Crane", CRANE)
	assert all(crane.get(k) == v for k, v in RESTORED_TERMS.items())
	previous = frappe.get_doc("Crane Timesheet", "TS-00075")
	old_settlement = frappe.get_doc("Crane Profit Settlement", previous.profit_settlement)
	old_snapshot = old_settlement.agreement_snapshot
	day = max(getdate(today()), getdate(crane.agreement_effective_from), getdate(add_days(old_settlement.to_date, 1)))
	company = crane.sharing_company
	cash = frappe.db.get_value("Account", {"company": company, "account_name": "HER1313 Cash"}, "name")
	mode = "HER1313 Cash"
	income = frappe.db.get_value("Account", {"company": company, "account_name": "HER1313 Rental Revenue"}, "name")
	assert cash and income
	before_cash = cash_balance(cash)
	assert before_cash >= 1500
	assignment = frappe.get_doc(dict(doctype="Crane Assignment", company=company, customer=previous.customer,
		location="تجربة استعادة توزيع الربحية التلقائي", assigned_cranes=[dict(crane=crane.name,
			start_date=day, expected_end_date=day, rental_rate_unit="Day", rental_rate=10000)])).insert()
	sheet = frappe.get_doc(dict(doctype="Crane Timesheet", crane=crane.name, assignment=assignment.name,
		driver=previous.driver, period_start=day, period_end=day,
		timesheet_entries=[dict(work_date=day, start_time="08:00", end_time="16:00", worked_hours=8)])).insert()
	sheet.submit()
	settlement = frappe.get_doc("Crane Profit Settlement", sheet.reload().profit_settlement)
	assert settlement.docstatus == 0
	template = frappe.get_doc("Expense Entry", "EXPE-00123")
	expense = frappe.get_doc(dict(doctype="Expense Entry", company=company, posting_date=day,
		crane=crane.name, crane_assignment=assignment.name, crane_timesheet=sheet.name,
		service_from_date=day, service_to_date=day, cost_center=crane.sharing_cost_center,
		mode_of_payment=mode, description="تجربة التوزيع التلقائي: تكلفة تشغيل مسجلة قبل فاتورة البيع",
		expenses=[dict(expense_entry_type=template.expenses[0].expense_entry_type, amount=1500)])).insert()
	expense.submit()
	invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=sheet.name)["name"])
	invoice.update(dict(posting_date=day, due_date=day, set_posting_time=1, cost_center=crane.sharing_cost_center,
		remarks="تجربة معتمدة: استحقاق الشركاء آليًا من الإيراد عند اعتماد فاتورة البيع"))
	invoice.set("taxes", [])
	for row in invoice.items:
		row.income_account = income
		row.cost_center = crane.sharing_cost_center
	invoice.save().submit()
	# No manual settlement submission: this must have happened with the invoice.
	settlement.reload()
	assert settlement.docstatus == 1 and settlement.journal_entry
	assert (settlement.revenue, settlement.operating_fee, settlement.operating_expenses,
		settlement.distributable_profit, settlement.company_retained, settlement.external_distribution) == (
		10000, 1000, 1500, 7500, 4000, 4500)
	journal = frappe.get_doc("Journal Entry", settlement.journal_entry)
	assert sum(flt(r.debit_in_account_currency) for r in journal.accounts if r.account == income) == 4500
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	receipt = get_payment_entry("Sales Invoice", invoice.name, bank_account=cash)
	receipt.update(dict(posting_date=day, reference_no="HER restored customer receipt", reference_date=day))
	receipt.insert().submit()
	partners = [r.shareholder for r in settlement.shares if not r.is_company]
	assert len(partners) == 3
	payments = []
	partial = None
	for partner, amount in [(partners[0], 500), (partners[0], 1000), (partners[1], 1500), (partners[2], 1500)]:
		payment = frappe.get_doc(make_partner_payment(settlement.name, shareholder=partner))
		payment.update(dict(paid_from=cash, posting_date=day, mode_of_payment=mode,
			reference_no="HER restored manual partner payment", reference_date=day,
			paid_amount=amount, received_amount=amount))
		payment.references[0].allocated_amount = amount
		payment.insert().submit()
		payments.append(payment.name)
		if partial is None:
			balance = next(r for r in settlement_payment_details(settlement.name)["balances"] if r["party"] == partners[0])
			assert (balance["paid_amount"], balance["outstanding_amount"]) == (500, 1000)
			partial = dict(payment=payment.name, paid=500, outstanding=1000)
	assert cash_balance(cash) - before_cash == 4000
	assert old_settlement.reload().agreement_snapshot == old_snapshot
	return dict(crane=crane.name, company=company, date=str(day), assignment=assignment.name,
		timesheet=sheet.name, expense=expense.name, sales_invoice=invoice.name,
		settlement=settlement.name, entitlement_journal=journal.name, customer_receipt=receipt.name,
		partner_payments=payments, partial_payment_check=partial,
		income_account=income, cash_account=cash, cash_before=before_cash,
		cash_after=cash_balance(cash), cash_increase=4000,
		revenue=10000, operating_fee=1000, costs=1500, residual=7500,
		company_retained=4000, partner_entitlement_each=1500, external_distribution=4500,
		previous_settlement=old_settlement.name, previous_snapshot_preserved=True)


def verify(result):
	settlement = frappe.get_doc("Crane Profit Settlement", result["settlement"])
	assert settlement.docstatus == 1
	assert (settlement.revenue, settlement.company_retained, settlement.external_distribution) == (10000, 4000, 4500)
	terms = json.loads(settlement.agreement_snapshot)
	assert all(terms[k] == v for k, v in RESTORED_TERMS.items())
	journal = frappe.get_doc("Journal Entry", result["entitlement_journal"])
	assert journal.docstatus == 1 and journal.total_debit == journal.total_credit == 4500
	assert {r.account for r in journal.accounts if r.debit_in_account_currency} == {result["income_account"]}
	assert all(r.party_type == "Shareholder" for r in journal.accounts if r.credit_in_account_currency)
	balances = settlement_payment_details(settlement.name)["balances"]
	assert len(balances) == 3 and all(r["entitlement"] == r["paid_amount"] == 1500 and r["outstanding_amount"] == 0 for r in balances)
	assert frappe.db.get_value("Sales Invoice", result["sales_invoice"], "outstanding_amount") == 0
	vouchers = [("Sales Invoice", result["sales_invoice"]), ("Journal Entry", result["entitlement_journal"]),
		("Journal Entry", frappe.db.get_value("Expense Entry", result["expense"], "journal_entry"))]
	vouchers += [("Payment Entry", name) for name in [result["customer_receipt"], *result["partner_payments"]]]
	for doctype, name in vouchers:
		rows = frappe.get_all("GL Entry", filters={"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0}, fields=["debit", "credit"])
		assert rows and flt(sum(flt(r.debit) - flt(r.credit) for r in rows), 2) == 0
	result.update(verified=True, balanced_vouchers=len(vouchers))
	return result
