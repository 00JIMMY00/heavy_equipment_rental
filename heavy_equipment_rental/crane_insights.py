"""Read-only fleet indicators for the stakeholder workspace."""

import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

import frappe
from frappe.utils import cint, flt, getdate, today


TITLE = "Crane Insights"
BLOCK = "Crane Fleet Overview"
TEMPLATE = Path(__file__).parent / "templates" / "crane_insights"


def install_workspace():
    block = frappe.get_doc("Custom HTML Block", BLOCK) if frappe.db.exists("Custom HTML Block", BLOCK) else frappe.new_doc("Custom HTML Block")
    assets = {field: (TEMPLATE / filename).read_text() for field, filename in (
        ("html", "overview.html"), ("style", "overview.css"), ("script", "overview.js")
    )}
    if block.is_new() or any(block.get(key) != value for key, value in assets.items()):
        block.update(assets)
        block.private = 0
        if block.is_new():
            block.insert(set_name=BLOCK, ignore_permissions=True)
        else:
            block.save(ignore_permissions=True)

    if not frappe.db.exists("Workspace", TITLE):
        frappe.get_doc({
            "doctype": "Workspace", "label": TITLE, "title": TITLE, "public": 1, "icon": "dashboard",
            "roles": [{"role": role} for role in ("System Manager", "Projects Manager", "Projects User", "Accounts Manager")],
            "custom_blocks": [{"custom_block_name": BLOCK, "label": BLOCK}],
            "content": json.dumps([{"id": "fleet-overview", "type": "custom_block", "data": {
                "custom_block_name": BLOCK, "col": 12
            }}]),
        }).insert(ignore_permissions=True)


def crane_expenses(cranes, start, end):
    if not frappe.has_permission("Grouped Expense", "read"):
        return None

    rows = []
    if cranes:
        rows = frappe.get_list(
            "Grouped Expense",
            fields=[
                "name", "crane", "currency", "company",
                "items.posting_date as posting_date", "items.description as description",
                "items.amount as amount", "items.idx as row_number",
            ],
            filters=[
                ["Grouped Expense", "docstatus", "=", 1],
                ["Grouped Expense", "crane", "in", list(cranes)],
                ["Grouped Expense Item", "posting_date", "between", [start, end]],
            ],
            order_by="`tabGrouped Expense Item`.posting_date desc, `tabGrouped Expense`.name, `tabGrouped Expense Item`.idx",
            limit_page_length=0,
        )

    totals = Counter()
    batches = set()
    charged_cranes = set()
    for row in rows:
        row.currency = row.currency or frappe.get_cached_value("Company", row.company, "default_currency")
        totals[row.currency] += flt(row.amount)
        batches.add(row.name)
        charged_cranes.add(row.crane)
    return {"totals": totals, "batches": len(batches), "charged_cranes": len(charged_cranes), "rows": rows}


@frappe.whitelist()
def get_overview(days=30):
    days = cint(days)
    if days not in (7, 30, 90):
        frappe.throw(frappe._("Choose a supported reporting period."))
    frappe.has_permission("Crane", "read", throw=True)
    end = getdate(today())
    start = end - timedelta(days=days - 1)
    fleet = frappe.get_list("Crane", fields=["name", "crane_name", "operational_condition"], limit_page_length=0)
    names = {row.name: row.crane_name or row.name for row in fleet}
    conditions = Counter(row.operational_condition or "Unspecified" for row in fleet)
    result = {"as_of": end, "start": start, "fleet": len(fleet), "conditions": conditions, "work": None}
    result["cranes"] = sorted(fleet, key=lambda row: (names[row.name].casefold(), row.name))
    result["expenses"] = crane_expenses(names, start, end)
    if not frappe.has_permission("Crane Timesheet", "read"):
        return result

    sheets = frappe.get_list("Crane Timesheet", fields=["crane", "period_end", "total_crane_billable_hours"],
        filters={"docstatus": 1, "period_end": ["between", [start, end]]}, limit_page_length=0)
    daily = [0.0] * days
    by_crane = Counter()
    for sheet in sheets:
        if sheet.crane in names:
            hours = flt(sheet.total_crane_billable_hours)
            daily[(getdate(sheet.period_end) - start).days] += hours
            if hours > 0:
                by_crane[sheet.crane] += hours
    result["work"] = {
        "hours": sum(daily), "active": len(by_crane), "daily": daily,
        "leaders": [{"name": crane, "label": names[crane], "hours": hours}
            for crane, hours in sorted(by_crane.items(), key=lambda pair: (-pair[1], pair[0]))[:5]],
    }
    return result
