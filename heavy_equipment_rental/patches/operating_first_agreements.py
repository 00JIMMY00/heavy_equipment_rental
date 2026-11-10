"""Mark old agreements without rewriting their history, sources or settlements."""

import json

import frappe

from heavy_equipment_rental.profit_sharing import LEGACY_NET


def execute():
    for name, history in frappe.get_all("Crane", filters={"agreement_history": ["is", "set"]},
                                        fields=["name", "agreement_history"], as_list=True):
        versions = json.loads(history or "[]")
        if versions and "calculation_method" not in versions[-1]:
            frappe.db.set_value("Crane", name, dict(sharing_calculation=LEGACY_NET,
                                operating_percentage=0), update_modified=False)
    for row in frappe.get_all("Crane Profit Settlement", fields=["name", "calculation_method", "revenue"]):
        if row.calculation_method:
            continue
        shares = frappe.get_all("Crane Settlement Share", filters={"parent": row.name,
            "parenttype": "Crane Profit Settlement"}, fields=["name", "amount", "is_company"])
        for share in shares:
            frappe.db.set_value("Crane Settlement Share", share.name, dict(
                residual_amount=share.amount, operating_amount=0), update_modified=False)
        frappe.db.set_value("Crane Profit Settlement", row.name, dict(
            calculation_method=LEGACY_NET, operating_percentage=0, operating_fee=0,
            balance_after_operating=row.revenue,
            company_retained=sum(s.amount for s in shares if s.is_company)), update_modified=False)
