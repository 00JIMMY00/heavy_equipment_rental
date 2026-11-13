"""Preserve previous hire terms and initialize per-timesheet purchase opt-in."""

import frappe


def execute():
    for row in frappe.get_all("Crane Timesheet", fields=[
        "name", "docstatus", "crane_ownership_type", "legacy_purchase_terms",
        "period_start", "period_end", "rental_rate_unit", "purchase_rate",
    ]):
        if row.crane_ownership_type != "Rented":
            frappe.db.set_value("Crane Timesheet", row.name, "rented", 0, update_modified=False)
            continue
        terms = frappe.parse_json(row.legacy_purchase_terms) if row.legacy_purchase_terms else {}
        if "before_worked_hour_purchasing" in terms:
            continue
        terms["before_worked_hour_purchasing"] = {
            "basis": "inclusive_period", "period_start": row.period_start,
            "period_end": row.period_end, "unit": row.rental_rate_unit,
            "purchase_rate": row.purchase_rate,
        }
        values = {"rented": 1, "legacy_purchase_terms": frappe.as_json(terms)}
        # Day/Month draft prices must be entered again as hourly prices.
        if row.docstatus == 0 and row.rental_rate_unit != "Hour":
            values["purchase_rate"] = 0
        frappe.db.set_value("Crane Timesheet", row.name, values, update_modified=False)
