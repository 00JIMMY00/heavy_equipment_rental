"""Explicit, repeatable demo data. Never called by installation or migration."""

import frappe
from frappe.utils import add_days, getdate

from heavy_equipment_rental.billing import generate_sales_invoice


DEMO_LOCATION = "HER DEMO - One crane rental cycle"


def create_rental_cycle(company, start_date="2026-10-25"):
    """Run manually on a development site; all records use ordinary controllers."""
    frappe.only_for("System Manager")
    existing = frappe.db.get_value("Crane Assignment", {"company": company, "location": DEMO_LOCATION}, "name")
    if existing:
        return describe_cycle(existing)
    frappe.db.savepoint("her_demo_cycle")
    try:
        result = _create_cycle(company, start_date)
    except Exception:
        frappe.db.rollback(save_point="her_demo_cycle")
        raise
    return result


def _create_cycle(company, start_date, *, location=None, daily_rate=5000,
                  tax_amount=0, expense_amounts=None, rental_days=3):
    company_doc = frappe.get_doc("Company", company)
    start = getdate(start_date)
    if not isinstance(rental_days, int) or rental_days < 1:
        frappe.throw("The demo rental duration must be a positive whole number of days.")
    end = add_days(start, rental_days - 1)
    amounts = expense_amounts or (1500, 500, 1200, 300)
    if len(amounts) != 4:
        frappe.throw("The demo requires four expense amounts.")
    cash_parent = frappe.db.get_value("Account", {
        "company": company, "account_type": "Cash", "is_group": 1,
    }, "name")
    if not cash_parent:
        cash_parent = frappe.db.get_value("Account", company_doc.default_cash_account, "parent_account")
    if not cash_parent:
        frappe.throw("Configure the company's default cash account before creating the demo.")
    modes = {}
    accounts = {}
    for kind in ("Cash", "Driver Custody"):
        title = "HER Demo " + kind
        account = frappe.db.get_value("Account", {"company": company, "account_name": title}, "name")
        if not account:
            account = frappe.get_doc(dict(doctype="Account", account_name=title, company=company,
                parent_account=cash_parent, account_type="Cash", account_currency=company_doc.default_currency)).insert().name
        mode_name = title + " - " + company_doc.abbr
        if not frappe.db.exists("Mode of Payment", mode_name):
            frappe.get_doc(dict(doctype="Mode of Payment", mode_of_payment=mode_name, type="Cash", enabled=1,
                accounts=[dict(company=company, default_account=account)])).insert()
        elif frappe.db.get_value("Mode of Payment Account", {"parent": mode_name, "company": company}, "default_account") != account:
            frappe.throw("Demo payment mode has a different account; review it before continuing.")
        modes[kind], accounts[kind] = mode_name, account
    customer = frappe.get_doc(dict(doctype="Customer", customer_name="HER DEMO Rental Customer",
        customer_type="Company", customer_group=frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
        territory=frappe.db.get_value("Territory", {"is_group": 0}, "name"))).insert()
    employee = frappe.get_doc(dict(doctype="Employee", first_name="HER DEMO Operator", company=company,
        gender=frappe.db.get_value("Gender", {}, "name"), date_of_birth="1990-01-01",
        date_of_joining="2020-01-01", status="Active")).insert()
    crane = frappe.get_doc(dict(doctype="Crane", crane_name="HER DEMO 50 Ton Crane",
        capacity_tons=50, ownership_type="Owned", operational_condition="Operational",
        license_plate="HER-DEMO-001", period_prices=[dict(period="Day", price=daily_rate)])).insert()
    assignment = frappe.get_doc(dict(doctype="Crane Assignment", company=company,
        customer=customer.name, location=location or DEMO_LOCATION, assigned_cranes=[dict(crane=crane.name,
            start_date=start, expected_end_date=end, rental_rate_unit="Day", rental_rate=daily_rate)])).insert()
    sheet = frappe.get_doc(dict(doctype="Crane Timesheet", assignment=assignment.name, crane=crane.name,
        driver=employee.name, period_start=start, period_end=end, timesheet_entries=[
            dict(work_date=add_days(start, offset), start_time="08:00", end_time="16:00")
            for offset in range(rental_days)])).insert()
    sheet.submit()
    invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=sheet.name)["name"])
    invoice.set_posting_time = 1
    invoice.posting_date = end
    invoice.due_date = end
    invoice.set("taxes", [])
    if tax_amount:
        account = frappe.db.get_value("Account", {"company": company, "account_type": "Tax",
            "is_group": 0, "disabled": 0}, "name")
        if not account:
            frappe.throw("Configure a Tax account before creating the taxed operating demo.")
        invoice.append("taxes", dict(charge_type="Actual", account_head=account,
            tax_amount=tax_amount, description="HER DEMO contractual Grand Total example",
            cost_center=company_doc.cost_center))
    invoice.save()
    invoice.submit()
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    receipt = get_payment_entry("Sales Invoice", invoice.name, bank_account=accounts["Cash"])
    receipt.posting_date = end
    receipt.mode_of_payment = modes["Cash"]
    receipt.reference_no = "HER DEMO customer receipt"
    receipt.reference_date = end
    receipt.insert()
    receipt.submit()
    transfer = frappe.get_doc(dict(doctype="Treasury Transaction", company=company, posting_date=end,
        mode_of_payment=modes["Cash"], destination_account=accounts["Driver Custody"], amount=sum(amounts[2:]) + 1500,
        description="HER DEMO custody funding; transfer, not an expense")).insert()
    transfer.submit()
    for (title, kind), amount in zip((("Fuel", "Cash"), ("Transport", "Cash"),
                                    ("Operator Allowance", "Driver Custody"), ("Site Supplies", "Driver Custody")), amounts):
        expense_type = frappe.db.get_value("Expense Entry Type", {"company": company, "title": "HER DEMO " + title}, "name")
        if not expense_type:
            expense_type = frappe.get_doc(dict(doctype="Expense Entry Type", company=company,
                title="HER DEMO " + title, enabled=1, account=company_doc.default_expense_account)).insert().name
        expense = frappe.get_doc(dict(doctype="Expense Entry", company=company, posting_date=end,
            crane=crane.name, crane_assignment=assignment.name, employee=employee.name,
            description="HER DEMO " + title + " paid from " + kind, mode_of_payment=modes[kind],
            expenses=[dict(expense_entry_type=expense_type, amount=amount)])).insert()
        expense.submit()
    assignment.add_comment("Info", f"Simulated rental cycle: {rental_days} days × {daily_rate}; invoice Grand Total "
                           f"{invoice.base_grand_total}; costs {sum(amounts)}. Treasury transfers are not costs.")
    result = describe_cycle(assignment.name)
    result.update(customer_receipt=receipt.name, treasury_transfer=transfer.name)
    return result


def describe_cycle(assignment):
    rental = frappe.get_doc("Crane Assignment", assignment)
    sheets = frappe.get_all("Crane Timesheet", filters={"assignment": assignment},
                            fields=["name", "sales_invoice", "total_crane_billable_hours"])
    return dict(assignment=assignment, company=rental.company, crane=rental.assigned_cranes[0].crane,
                customer=rental.customer, timesheets=sheets,
                expenses=frappe.get_all("Expense Entry", filters={"crane_assignment": assignment}, pluck="name"),
                from_date=str(rental.assigned_cranes[0].start_date),
                to_date=str(rental.assigned_cranes[0].expected_end_date),
                report="/app/query-report/Crane%20Rental%20Profitability")
