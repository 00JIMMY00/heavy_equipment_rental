"""Link imported transfers to their explicit workbook categories; retain postings."""

import frappe

from heavy_equipment_rental.treasury_workbook import ensure_workbook_cost_center


def execute():
    # First-time installations have no import metadata until after_migrate setup.
    if not frappe.db.has_column("Treasury Transaction", "her_workbook_batch"):
        return
    for row in frappe.get_all("Treasury Transaction", filters={
        "her_workbook_batch": ["is", "set"], "her_workbook_category": ["is", "set"],
        "cost_center": ["is", "not set"],
    }, fields=["name", "company", "her_workbook_category"]):
        company = frappe.get_doc("Company", row.company)
        center = ensure_workbook_cost_center(company, row.her_workbook_category)
        # This fills only source attribution. Never rewrite submitted journals,
        # GL dimensions/amounts, or an already assigned Cost Center.
        frappe.db.set_value("Treasury Transaction", row.name, "cost_center", center,
                            update_modified=False)
