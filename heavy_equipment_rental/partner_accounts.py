"""Native Shareholder identities and company-specific partner payable defaults."""

import copy

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install():
    create_custom_fields({
        "Company": [dict(fieldname="crane_partner_payable_account", fieldtype="Link",
            label="Default Crane Partners Account", options="Account", insert_after="default_payable_account")],
        "Shareholder": [dict(fieldname="crane_partner_supplier", fieldtype="Link", label="Legacy Partner Supplier",
            options="Supplier", insert_after="company", read_only=1, no_copy=1),
            dict(fieldname="accounts", fieldtype="Table", label="Partner Accounts", options="Party Account",
                 insert_after="crane_partner_supplier")],
        "Payment Entry": [dict(fieldname="crane_profit_settlement", fieldtype="Link", label="Crane Profit Settlement",
            options="Crane Profit Settlement", insert_after="party", read_only=1, no_copy=1),
            dict(fieldname="crane_timesheet", fieldtype="Link", label="Crane Timesheet", options="Crane Timesheet",
                 insert_after="crane_profit_settlement", read_only=1, no_copy=1),
            dict(fieldname="crane", fieldtype="Link", label="Crane", options="Crane",
                 insert_after="crane_timesheet", read_only=1, no_copy=1)],
    }, update=True)
    for company in frappe.get_all("Company", pluck="name"):
        default_account(company)


def default_account(company):
    existing = frappe.db.get_value("Company", company, "crane_partner_payable_account")
    if existing:
        return existing
    # Keep partner current balances under liabilities, separate from supplier trade debt.
    parent = frappe.db.get_value("Account", {"company": company, "is_group": 1,
        "account_name": "Current Liabilities"}, "name")
    if not parent:
        parent = frappe.db.get_value("Account", {"company": company, "is_group": 1,
            "root_type": "Liability"}, "name", order_by="lft desc")
    if not parent:
        frappe.throw(_("Company {0} needs a Liability group for the Partners account.").format(company))
    name = frappe.db.get_value("Account", {"company": company, "account_name": "Partners", "is_group": 0}, "name")
    if not name:
        name = frappe.get_doc(dict(doctype="Account", account_name="Partners", company=company,
            parent_account=parent, account_type="Payable",
            account_currency=frappe.get_cached_value("Company", company, "default_currency"))).insert(ignore_permissions=True).name
    account = frappe.get_doc("Account", name)
    if account.account_type != "Payable" or account.disabled:
        frappe.throw(_("The Partners account in {0} must be an enabled Payable account.").format(company))
    frappe.db.set_value("Company", company, "crane_partner_payable_account", name, update_modified=False)
    return name


@frappe.whitelist()
def agreement_defaults(company):
    frappe.get_doc("Company", company).check_permission("read")
    return dict(partner_payable_account=default_account(company),
        sharing_cost_center=frappe.get_cached_value("Company", company, "cost_center"))


def shareholder_for_supplier(supplier, company):
    """Idempotent conversion; supplier records and historical ledgers stay intact."""
    name = frappe.db.get_value("Shareholder", {"crane_partner_supplier": supplier, "company": company}, "name")
    if name:
        return name
    source = frappe.get_doc("Supplier", supplier)
    source.check_permission("read")
    if source.disabled:
        frappe.throw(_("Partner Suppliers must be enabled."))
    return frappe.get_doc(dict(doctype="Shareholder", title=source.supplier_name, company=company,
        crane_partner_supplier=supplier, accounts=[dict(company=company, account=default_account(company))]
    )).insert(ignore_permissions=True).name


def modern_agreement(agreement):
    agreement = copy.deepcopy(agreement)
    legacy_partners = any(not p["is_company"] and not p.get("shareholder") for p in agreement["partners"])
    if legacy_partners and agreement.get("payable_account") == frappe.get_cached_value("Company", agreement["company"], "default_payable_account"):
        agreement["payable_account"] = default_account(agreement["company"])
    for row in agreement["partners"]:
        if not row["is_company"]:
            row["shareholder"] = row.get("shareholder") or shareholder_for_supplier(row["supplier"], agreement["company"])
    if agreement.get("operating_partner") and not agreement.get("operating_shareholder"):
        agreement["operating_shareholder"] = shareholder_for_supplier(agreement["operating_partner"], agreement["company"])
    return agreement


def share_party(row):
    if row.get("ledger_party_type") == "Supplier":
        return "Supplier", row.supplier
    return ("Shareholder", row.shareholder) if row.get("shareholder") else ("Supplier", row.supplier)


def validate_shareholder(doc, method=None):
    if doc.company and not any(r.company == doc.company for r in doc.accounts):
        doc.append("accounts", dict(company=doc.company, account=default_account(doc.company)))
