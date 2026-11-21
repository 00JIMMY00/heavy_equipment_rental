"""Company fixtures for HER integration tests on an initialized development site."""
import frappe


def other_company(company):
    name = frappe.db.get_value("Company", {"name": ["!=", company]}, "name")
    if name:
        return name
    source = frappe.get_doc("Company", company)
    return frappe.get_doc(dict(
        doctype="Company", company_name="HER Test " + frappe.generate_hash(length=8),
        abbr="T" + frappe.generate_hash(length=4), default_currency=source.default_currency,
        country=source.country, create_chart_of_accounts_based_on="Standard Template",
        chart_of_accounts="Standard",
    )).insert().name
