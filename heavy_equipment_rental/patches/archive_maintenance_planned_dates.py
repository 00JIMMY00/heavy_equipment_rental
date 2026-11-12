"""Preserve removed planning dates without turning them into actual work dates."""
import frappe


def execute():
    fields = [f for f in ("planned_start_date", "planned_end_date")
              if frappe.db.has_column("Crane Maintenance", f)]
    if not fields:
        return
    for row in frappe.db.sql("SELECT name, legacy_planned_dates, " + ", ".join(fields) +
            " FROM `tabCrane Maintenance`", as_dict=True):
        dates = {f: row[f] for f in fields if row.get(f)}
        if dates and not row.legacy_planned_dates:
            frappe.db.set_value("Crane Maintenance", row.name, "legacy_planned_dates",
                frappe.as_json(dates), update_modified=False)
