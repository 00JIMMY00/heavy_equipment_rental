"""Explicit development-only example for the user's Crane 1313 request.

No install/migration hooks. Rehearse with run(); persist with run(commit=True).
"""
import json

import frappe
from frappe.utils import flt, getdate, strip_html

from heavy_equipment_rental.billing import generate_sales_invoice
from heavy_equipment_rental.crane_assets import asset_summary
from heavy_equipment_rental.crane_repairs import make_repair_document
from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement import make_partner_payment
from heavy_equipment_rental.partner_reporting import partner_balances

MARKER = "HER1313_RESULT="
TITLE = "ونش ١٣١٣"
COMPANY = "cranes company"
BUY_DATE = "2026-10-13"
START = "2026-11-11"
END = "2026-11-12"


def run(commit=False):
    frappe.only_for("System Manager")
    if frappe.local.site != "cranes-dev2.arab-erp.com":
        frappe.throw("This explicit example is restricted to the development site.")
    existing = frappe.db.get_value("Crane", {"crane_name": TITLE}, "name")
    if existing:
        for comment in frappe.get_all("Comment", filters={"reference_doctype": "Crane", "reference_name": existing}, pluck="content"):
            content = strip_html(comment)
            if content.startswith(MARKER):
                result = json.loads(content[len(MARKER):])
                return verify(result)
        frappe.throw("Crane 1313 already exists without this completed example marker; review it before proceeding.")
    try:
        from heavy_equipment_rental.rental_items import preserve_rental_income_defaults
        with preserve_rental_income_defaults():
            result = create()
        result = verify(result)
        if commit:
            frappe.get_doc("Crane", result["crane"]).add_comment("Info", MARKER + json.dumps(result, ensure_ascii=False, default=str))
            frappe.db.commit()
        else:
            frappe.db.rollback()
        return result
    except Exception:
        frappe.db.rollback()
        raise


def account(title, root, account_type=None):
    company = frappe.get_doc("Company", COMPANY)
    anchor = {"Cash": company.default_cash_account, "Stock": company.default_inventory_account,
              "Income Account": company.default_income_account}.get(account_type)
    if not anchor and account_type:
        anchor = frappe.db.get_value("Account", dict(company=COMPANY, account_type=account_type, is_group=0), "name")
    if not anchor and root == "Expense":
        anchor = company.default_expense_account
    parent = frappe.db.get_value("Account", anchor, "parent_account") if anchor else None
    parent = parent or frappe.db.get_value("Account", dict(company=COMPANY, root_type=root, is_group=1), "name", order_by="lft")
    values = dict(doctype="Account", account_name="HER1313 " + title, company=COMPANY,
        parent_account=parent, account_currency="EGP", is_group=0)
    if account_type:
        values["account_type"] = account_type
    return frappe.get_doc(values).insert().name


def invoice_payment(doctype, name, cash, date):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    payment = get_payment_entry(doctype, name, bank_account=cash)
    payment.posting_date = date
    payment.reference_no = "HER1313 " + doctype
    payment.reference_date = date
    payment.insert().submit()
    return payment.name


def create():
    company = frappe.get_doc("Company", COMPANY)
    assert company.default_currency == "EGP"
    assert not frappe.db.exists("Account", {"company": COMPANY, "account_name": "HER1313 Cash"})
    cc = frappe.get_doc(dict(doctype="Cost Center", cost_center_name="HER1313 ونش ١٣١٣",
        company=COMPANY, parent_cost_center=frappe.db.get_value("Cost Center", {"company": COMPANY, "is_group": 1}, "name"))).insert().name
    cash = account("Cash", "Asset", "Cash")
    equity = account("Demo Funding", "Equity")
    fixed = account("Company Crane Asset", "Asset", "Fixed Asset")
    accumulated = account("Accumulated Depreciation", "Asset", "Accumulated Depreciation")
    depreciation_expense = account("Depreciation", "Expense", "Depreciation")
    operating_expense = account("Operating Costs", "Expense")
    participation = account("Partner Participation", "Expense")
    income = account("Rental Revenue", "Income", "Income Account")
    inventory = account("Parts Inventory", "Asset", "Stock")
    mode = frappe.get_doc(dict(doctype="Mode of Payment", mode_of_payment="HER1313 Cash",
        type="Cash", enabled=1, accounts=[dict(company=COMPANY, default_account=cash)])).insert().name
    funding = frappe.get_doc(dict(doctype="Journal Entry", company=COMPANY, posting_date=BUY_DATE,
        user_remark="HER1313 تمويل تجريبي للشركة لشراء حصتها، وليس مساهمة مستنتجة من نسب الشركاء",
        accounts=[dict(account=cash, debit_in_account_currency=300000, cost_center=cc),
                  dict(account=equity, credit_in_account_currency=300000, cost_center=cc)])).insert()
    funding.submit()
    category = frappe.get_doc(dict(doctype="Asset Category", asset_category_name="HER1313 Crane Assets",
        enable_cwip_accounting=0, accounts=[dict(company_name=COMPANY, fixed_asset_account=fixed,
            accumulated_depreciation_account=accumulated, depreciation_expense_account=depreciation_expense)])).insert()
    group = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    item = frappe.get_doc(dict(doctype="Item", item_code="HER1313-CRANE-FA", item_name="ونش تجريبي - حصة الشركة",
        item_group=group, stock_uom="Nos", is_stock_item=0, is_fixed_asset=1,
        auto_create_assets=1, asset_naming_series="ACC-ASS-.YYYY.-", asset_category=category.name)).insert()
    supplier = frappe.get_doc(dict(doctype="Supplier", supplier_name="HER1313 مورد تجريبي",
        supplier_type="Company", supplier_group=frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))).insert()
    location = frappe.get_doc(dict(doctype="Location", location_name="HER1313 ساحة الونش")).insert()
    purchase = frappe.get_doc(dict(doctype="Purchase Invoice", company=COMPANY, supplier=supplier.name,
        posting_date=BUY_DATE, set_posting_time=1, update_stock=1, currency="EGP", cost_center=cc,
        remarks="HER1313 شراء حصة الشركة 40% فقط؛ كامل الونش 750000، حصة الشركة 300000",
        items=[dict(item_code=item.name, qty=1, rate=300000, asset_location=location.name,
            cost_center=cc, expense_account=fixed)])).insert()
    purchase.submit()
    asset = frappe.get_doc("Asset", {"purchase_invoice": purchase.name, "item_code": item.name})
    asset.update(dict(asset_name=TITLE + " - حصة الشركة 40%", asset_owner="Company", asset_owner_company=COMPANY,
        available_for_use_date=BUY_DATE, cost_center=cc, calculate_depreciation=1))
    asset.set("finance_books", [dict(finance_book=company.default_finance_book, depreciation_method="Straight Line",
        frequency_of_depreciation=1, total_number_of_depreciations=60, expected_value_after_useful_life=0,
        daily_prorata_based=0, depreciation_start_date=END)])
    asset.save().submit()
    asset_payment = invoice_payment("Purchase Invoice", purchase.name, cash, BUY_DATE)
    partners = [frappe.get_doc(dict(doctype="Shareholder", title=f"HER1313 شريك تجريبي {i}", company=COMPANY)).insert().name for i in (1,2,3)]
    crane = frappe.get_doc(dict(doctype="Crane", crane_name=TITLE, capacity_tons=50, license_plate="DEMO-1313",
        ownership_type="Shared Ownership", sharing_company=COMPANY, agreement_effective_from=BUY_DATE,
        operator_type="Our Company", operating_percentage=10, settlement_approval="Review Before Posting",
        settlement_revenue_basis="Net Revenue", distribution_posting="Partner Expense",
        profit_allocation_account=participation, sharing_cost_center=cc, include_depreciation=0,
        ownership_partners=[dict(is_company=1, ownership_percentage=40, profit_percentage=40)] + [
            dict(shareholder=name, ownership_percentage=20, profit_percentage=20) for name in partners],
        asset=asset.name, period_prices=[dict(period="Day", price=50000)])).insert()
    customer = frappe.get_doc(dict(doctype="Customer", customer_name="HER1313 عميل تجريبي",
        customer_type="Company", customer_group=frappe.db.get_value("Customer Group", {"is_group":0},"name"),
        territory=frappe.db.get_value("Territory", {"is_group":0},"name"))).insert()
    driver = frappe.get_doc(dict(doctype="Employee", first_name="HER1313 مشغل تجريبي", company=COMPANY,
        gender=frappe.db.get_value("Gender", {}, "name"), date_of_birth="1990-01-01",
        date_of_joining="2026-01-01", status="Active")).insert()
    assignment = frappe.get_doc(dict(doctype="Crane Assignment", company=COMPANY, customer=customer.name,
        location="HER1313 موقع إيجار تجريبي", assigned_cranes=[dict(crane=crane.name, start_date=START,
            expected_end_date=END, rental_rate_unit="Day", rental_rate=50000)])).insert()
    sheet = frappe.get_doc(dict(doctype="Crane Timesheet", crane=crane.name, assignment=assignment.name,
        driver=driver.name, period_start=START, period_end=END, timesheet_entries=[
            dict(work_date=day,start_time="08:00",end_time="16:00",worked_hours=8) for day in (START,END)])).insert()
    sheet.submit()
    warehouse = frappe.get_doc(dict(doctype="Warehouse", warehouse_name="HER1313 Parts", company=COMPANY, account=inventory)).insert()
    part = frappe.get_doc(dict(doctype="Item", item_code="HER1313-PART", item_name="HER1313 قطعة إصلاح تجريبية",
        item_group=group, stock_uom="Nos", is_stock_item=1, valuation_method="FIFO")).insert()
    parts_invoice = frappe.get_doc(dict(doctype="Purchase Invoice", company=COMPANY, supplier=supplier.name,
        posting_date=START, set_posting_time=1, update_stock=1, cost_center=cc,
        items=[dict(item_code=part.name,qty=10,rate=200,warehouse=warehouse.name,cost_center=cc)])).insert()
    parts_invoice.submit()
    sales=frappe.get_doc("Sales Invoice",generate_sales_invoice(timesheet=sheet.name)["name"])
    sales.set_posting_time=1
    sales.posting_date=sales.due_date=END
    sales.cost_center=cc
    sales.set("taxes",[])
    for row in sales.items:
        row.income_account=income
        row.cost_center=cc
    sales.save().submit()
    customer_receipt=invoice_payment("Sales Invoice",sales.name,cash,END)
    parts_payment = invoice_payment("Purchase Invoice", parts_invoice.name, cash, END)
    repair = frappe.get_doc(dict(doctype="Crane Maintenance", crane=crane.name, company=COMPANY,
        crane_assignment=assignment.name, crane_timesheet=sheet.name, maintenance_type="Corrective",
        cost_treatment="Operating Expense", actual_start_date=END, actual_end_date=END,
        status="In Progress", description="HER1313 صيانة عادية من مخزون الشركة - 2000")).insert()
    stock = frappe.get_doc(make_repair_document(repair.name,"Stock Entry"))
    stock.append("items", dict(item_code=part.name,s_warehouse=warehouse.name,qty=10,
        expense_account=operating_expense,cost_center=cc))
    stock.insert().submit()
    repair.status="Completed"
    repair.save()
    expenses=[]
    for title,amount in (("وقود",8000),("أجر سائق",4000),("نقل",1000)):
        expense_type=frappe.get_doc(dict(doctype="Expense Entry Type",title="HER1313 "+title,
            company=COMPANY,account=operating_expense,enabled=1)).insert()
        expense=frappe.get_doc(dict(doctype="Expense Entry",company=COMPANY,posting_date=END,
            crane=crane.name,crane_assignment=assignment.name,crane_timesheet=sheet.name,
            service_from_date=START,service_to_date=END,cost_center=cc,mode_of_payment=mode,
            description="HER1313 "+title,employee=driver.name if title=="أجر سائق" else None,expenses=[dict(expense_entry_type=expense_type.name,amount=amount)])).insert()
        expense.submit()
        expenses.append(expense.name)
    from erpnext.assets.doctype.asset.depreciation import make_depreciation_entry
    schedule=frappe.db.get_value("Asset Depreciation Schedule",{"asset":asset.name,"status":"Active"},"name")
    schedule_doc=make_depreciation_entry(schedule,END)
    depreciation_journal=schedule_doc.depreciation_schedule[0].journal_entry
    assert depreciation_journal, "Native depreciation was not posted"
    assert flt(frappe.db.get_value("Journal Entry",depreciation_journal,"total_debit"),2)==5000
    settlement=frappe.get_doc("Crane Profit Settlement",sheet.reload().profit_settlement)
    settlement.posting_date=END
    settlement.costs_reviewed=1
    settlement.save().submit()
    partner_payments=[]
    for name in partners:
        payment=frappe.get_doc(make_partner_payment(settlement.name,shareholder=name))
        payment.paid_from=cash
        payment.posting_date=END
        payment.reference_no="HER1313 دفع مستحق الشريك"
        payment.reference_date=END
        payment.mode_of_payment=mode
        payment.insert().submit()
        partner_payments.append(payment.name)
    return dict(company=COMPANY,currency="EGP",crane=crane.name,asset=asset.name,company_cost=300000,
        physical_reference_cost=750000,ownership=[40,20,20,20],operating_percentage=10,
        customer=customer.name,partners=partners,assignment=assignment.name,timesheet=sheet.name,
        acquisition_invoice=purchase.name,acquisition_payment=asset_payment,funding_journal=funding.name,
        parts_invoice=parts_invoice.name,parts_payment=parts_payment,maintenance=repair.name,stock_issue=stock.name,
        expenses=expenses,depreciation_schedule=schedule,depreciation_journal=depreciation_journal,
        sales_invoice=sales.name,customer_receipt=customer_receipt,settlement=settlement.name,
        entitlement_journal=settlement.journal_entry,partner_payments=partner_payments,
        start_date=START,end_date=END,cost_center=cc,warehouse=warehouse.name,part=part.name,
        accounts=dict(cash=cash,equity=equity,fixed=fixed,accumulated=accumulated,depreciation=depreciation_expense,
            operating=operating_expense,participation=participation,income=income,inventory=inventory))


def verify(result):
    settlement=frappe.get_doc("Crane Profit Settlement",result["settlement"])
    assert settlement.docstatus==1
    assert (settlement.revenue,settlement.operating_fee,settlement.operating_expenses,settlement.distributable_profit)==(100000,10000,15000,75000)
    assert (settlement.company_retained,settlement.external_distribution)==(40000,45000)
    balances=partner_balances(settlement,END)
    assert len(balances)==3 and all(b["entitlement"]==15000 and b["outstanding_amount"]==0 for b in balances)
    for invoice in (result["acquisition_invoice"],result["parts_invoice"]):
        assert frappe.db.get_value("Purchase Invoice",invoice,["docstatus","outstanding_amount"])==(1,0)
    assert frappe.db.get_value("Sales Invoice",result["sales_invoice"],["docstatus","outstanding_amount"])==(1,0)
    summary=asset_summary(result["crane"])
    assert (summary["gross_purchase_amount"],summary["book_value"],summary["company_ownership_percentage"])==(300000,295000,40)
    assert frappe.db.get_value("Bin",{"item_code":result["part"],"warehouse":result["warehouse"]},"actual_qty")==0
    totals={}
    vouchers=set()
    for key,acct in result["accounts"].items():
        rows=frappe.get_all("GL Entry",filters={"account":acct,"is_cancelled":0},fields=["voucher_type","voucher_no","debit","credit"])
        totals[key]=flt(sum(flt(r.debit)-flt(r.credit) for r in rows),2)
        vouchers.update((r.voucher_type,r.voucher_no) for r in rows)
    cash_movements = frappe.get_all("GL Entry", filters={"account":result["accounts"]["cash"],"is_cancelled":0},
        fields=["posting_date","creation","name","debit","credit"], order_by="posting_date, creation, name")
    running_cash = 0
    for movement in cash_movements:
        running_cash += flt(movement.debit)-flt(movement.credit)
        assert running_cash >= 0, "Demo Cash must not rely on an unexplained overdraft"
    assert totals==dict(cash=40000,equity=-300000,fixed=300000,accumulated=-5000,depreciation=5000,
        operating=15000,participation=45000,income=-100000,inventory=0),totals
    for doctype,name in vouchers:
        rows=frappe.get_all("GL Entry",filters={"voucher_type":doctype,"voucher_no":name,"is_cancelled":0},fields=["debit","credit"])
        assert flt(sum(flt(r.debit)-flt(r.credit) for r in rows),2)==0,(doctype,name)
    from heavy_equipment_rental.heavy_equipment_rental.report.crane_rental_profitability.crane_rental_profitability import execute
    report=execute(dict(company=COMPANY,crane=result["crane"],from_date=START,to_date=END))
    assert [s["value"] for s in report[4]]==[100000,20000,80000]
    assignment_report=execute(dict(company=COMPANY,crane=result["crane"],assignment=result["assignment"],from_date=START,to_date=END))
    assert [s["value"] for s in assignment_report[4]]==[100000,15000,85000]
    result.update(assignment_report_totals=[s["value"] for s in assignment_report[4]],
        vouchers=[dict(doctype=dt,name=name) for dt,name in sorted(vouchers)],verified=True,settlement_revenue=100000,shared_costs=15000,operating_fee=10000,
        residual=75000,company_before_depreciation=40000,company_net_profit=35000,
        company_book_value=295000,cash_balance=40000,partner_entitlement_each=15000,
        partner_balances=balances,account_balances=totals,balanced_vouchers=len(vouchers),
        report_totals=[s["value"] for s in report[4]])
    return result
