"""One automatic settlement per Timesheet, posted atomically with its invoice."""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.profit_sharing import allocate_amount, collect_sources
from heavy_equipment_rental.rental_validation import lock_cranes


def active_settlement(timesheet):
    return frappe.db.get_value("Crane Profit Settlement", {"timesheet": timesheet, "docstatus": ["!=", 2]}, "name")


def ensure_settlement(sheet, method=None):
    if sheet.docstatus != 1 or not frappe.db.get_value("Crane", sheet.crane, "enable_profit_sharing"):
        return
    lock_cranes([sheet.crane])
    existing = active_settlement(sheet.name)
    if existing:
        doc = frappe.get_doc("Crane Profit Settlement", existing)
    else:
        # A historical period settlement can cover several Timesheets. Never pay it twice.
        historical = frappe.db.get_value("Crane Timesheet", sheet.name, "profit_settlement")
        if historical and frappe.db.get_value("Crane Profit Settlement", historical, "docstatus") == 1:
            return frappe.get_doc("Crane Profit Settlement", historical)
        doc = frappe.get_doc(dict(doctype="Crane Profit Settlement", timesheet=sheet.name,
            crane=sheet.crane, from_date=sheet.period_start, to_date=sheet.period_end,
            posting_date=max(getdate(today()), getdate(sheet.period_end))))
        doc.insert(ignore_permissions=True)
    frappe.db.set_value("Crane Timesheet", sheet.name, "profit_settlement", doc.name, update_modified=False)
    sheet.profit_settlement = doc.name
    if doc.docstatus == 0 and doc.sales_invoice != sheet.sales_invoice:
        doc.sales_invoice = sheet.sales_invoice
        doc.save(ignore_permissions=True)
    if sheet.sales_invoice and frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") == 1 and doc.docstatus == 0:
        # Explicit automation authorization: calculations still enforce source read and
        # journal create/submit permissions. Failure rolls the invoice transaction back.
        doc.flags.ignore_permissions = True
        doc.posting_date = max(getdate(today()), getdate(sheet.period_end),
            getdate(frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "posting_date")))
        doc.submit()
    return doc


def invoice_submitted(invoice, method=None):
    sheets = frappe.get_all("Crane Timesheet", filters={"sales_invoice": invoice.name, "docstatus": 1},
        fields=["name", "crane"], order_by="crane, name")
    lock_cranes([s.crane for s in sheets])
    for row in sheets:
        sheet = frappe.get_doc("Crane Timesheet", row.name)
        sheet.check_permission("read")
        ensure_settlement(sheet)


def guard_timesheet(sheet, method=None):
    lock_cranes([sheet.crane])
    from heavy_equipment_rental.rental_expenses import matches
    for closed in frappe.get_all("Crane Profit Settlement", filters={"crane": sheet.crane, "docstatus": 1, "settlement_basis": "Timesheet"},
            fields=["name", "source_snapshot"]):
        for source in json.loads(closed.source_snapshot or "[]"):
            if source["doctype"] == "Expense Entry" and source.get("service_from_date") and matches(source, sheet):
                frappe.throw(_("Expense allocation is closed by settlement {0}. Cancel the affected settlement before changing its work.").format(closed.name))
    settled = frappe.db.get_value("Crane Profit Settlement", {"crane": sheet.crane, "docstatus": 1,
        "from_date": ["<=", sheet.period_end], "to_date": [">=", sheet.period_start]}, "name")
    if settled:
        frappe.throw(_("Timesheet period is covered by settlement {0}. Cancel the settlement before changing its work allocation.").format(settled))


def collect_timesheet_sources(sheet, company, grand_total):
    if not sheet.sales_invoice or frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "docstatus") != 1:
        return []
    invoice_day = frappe.db.get_value("Sales Invoice", sheet.sales_invoice, "posting_date")
    sources = collect_sources(sheet.crane, company, min(getdate(sheet.period_start), getdate(invoice_day)),
        max(getdate(today()), getdate(invoice_day), getdate(sheet.period_end)), grand_total=grand_total, include_expenses=False)
    from heavy_equipment_rental.rental_expenses import expense_sources, matches, check_posted
    expense_docs = {}
    for expense, source in expense_sources(sheet.crane, company):
        if matches(source, sheet):
            sources.append(source)
            expense_docs[expense.name] = expense
    all_sheets = frappe.get_all("Crane Timesheet", filters={"crane": sheet.crane, "docstatus": 1},
        fields=["name", "assignment", "period_start", "period_end", "sales_invoice", "purchase_invoice", "total_amount", "total_crane_billable_hours"],
        order_by="name")
    all_sheets = [s for s in all_sheets if frappe.get_cached_value("Crane Assignment", s.assignment, "company") in (None, "", company)]
    result = []
    for source in sources:
        kind = source["doctype"]
        if kind in ("Sales Invoice", "Purchase Invoice"):
            link = "sales_invoice" if kind == "Sales Invoice" else "purchase_invoice"
            original = frappe.db.get_value(kind, source["name"], "return_against") or source["name"]
            candidates = [s for s in all_sheets if s[link] == original]
            weight = "total_amount" if kind == "Sales Invoice" else "total_crane_billable_hours"
        elif kind == "Expense Entry":
            candidates = [s for s in all_sheets if matches(source, s)]
            check_posted(expense_docs[source["name"]])
            weight = "total_crane_billable_hours"
        else:
            day = getdate(source["posting_date"])
            candidates = [s for s in all_sheets if getdate(s.period_start) <= day <= getdate(s.period_end)]
            weight = "total_crane_billable_hours"
        if not candidates or sheet.name not in [s.name for s in candidates]:
            continue
        side = "revenue" if "revenue" in source else "expenses"
        weights = [max(flt(s[weight]), 0) for s in candidates]
        if not sum(weights):
            frappe.throw(_("Cannot allocate source {0}: linked Timesheets have zero billing weight.").format(source["name"]))
        # Company currency precision follows the settlement currency fields.
        precision = frappe.get_precision("Crane Profit Settlement", "revenue", currency=frappe.get_cached_value("Company", company, "default_currency"))
        amount = allocate_amount(source[side], weights, precision)[[s.name for s in candidates].index(sheet.name)]
        if amount:
            result.append(dict(source, **{side: amount}, source_amount=source[side],
                allocation_timesheets=[s.name for s in candidates], allocation_weights=weights))
    return result


def guard_source_snapshots(doc, cranes):
    """Invoice posting dates can differ from work dates: protect captured sources too."""
    if not cranes:
        return
    for row in frappe.get_all("Crane Profit Settlement", filters={"crane": ["in", list(cranes)], "docstatus": 1},
            fields=["name", "source_snapshot"]):
        if any(s["doctype"] == doc.doctype and s["name"] in (doc.name, doc.get("return_against"))
               for s in json.loads(row.source_snapshot or "[]")):
            frappe.throw(_("Source is included in settlement {0}. Cancel that settlement first.").format(row.name))


def validate_source_allocations(doc, sources):
    """Forbid mixing period closure with Timesheet allocation, and over-distribution."""
    previous = frappe.get_all("Crane Profit Settlement", filters={"crane": doc.crane, "docstatus": 1,
        "name": ["!=", doc.name]}, fields=["name", "timesheet", "settlement_basis", "source_snapshot"])
    for source in sources:
        key = (source["doctype"], source["name"], source.get("detail"))
        side = "revenue" if "revenue" in source else "expenses"
        used = 0
        for row in previous:
            for old in json.loads(row.source_snapshot or "[]"):
                if (old["doctype"], old["name"], old.get("detail")) != key:
                    continue
                if doc.settlement_basis != "Timesheet" or row.settlement_basis != "Timesheet":
                    separate_expense_periods = (source["doctype"] == "Expense Entry" and
                        doc.settlement_basis != "Timesheet" and row.settlement_basis != "Timesheet" and
                        source.get("allocation_from_date") and old.get("allocation_from_date") and
                        (getdate(source["allocation_from_date"]) > getdate(old["allocation_to_date"]) or
                         getdate(source["allocation_to_date"]) < getdate(old["allocation_from_date"])))
                    if not separate_expense_periods:
                        frappe.throw(_("Source {0} is already covered by settlement {1}.").format(source["name"], row.name))
                if (source.get("allocation_timesheets") and old.get("allocation_timesheets") and
                        (source["allocation_timesheets"] != old["allocation_timesheets"] or
                         source["allocation_weights"] != old["allocation_weights"])):
                    frappe.throw(_("Allocation of {0} changed after settlement {1}. Cancel the affected settlement first.").format(source["name"], row.name))
                used += flt(old.get(side))
        total = flt(source.get("source_amount", source.get(side)))
        if abs(flt(used + source.get(side, 0), doc.precision("revenue"))) > abs(total):
            frappe.throw(_("Source {0} would be distributed more than once.").format(source["name"]))
