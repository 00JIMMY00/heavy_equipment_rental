"""Choose rental work for maintenance and expenses without conflicting links."""

import frappe
from frappe import _
from frappe.utils import getdate, today


def window(doc):
    if doc.doctype == "Crane Maintenance":
        start = doc.actual_start_date or today()
        end = doc.actual_end_date or start
    else:
        start = doc.get("service_from_date") or doc.posting_date
        end = doc.get("service_to_date") or start
    return getdate(start), getdate(end)


@frappe.whitelist()
def rental_work_options(crane, start=None, end=None, company=None):
    frappe.get_doc("Crane", crane).check_permission("read")
    start, end = (getdate(start), getdate(end or start)) if start else (getdate("1900-01-01"), getdate("9999-12-31"))
    if start > end:
        frappe.throw(_("From Date must not be after To Date."))
    bookings = frappe.get_all("Assigned Crane", filters={"parenttype": "Crane Assignment", "crane": crane, "cancelled": 0,
        "start_date": ["<=", end], "expected_end_date": [">=", start]},
        fields=["parent", "start_date", "expected_end_date"], order_by="start_date, parent")
    assignments = []
    names = set()
    for row in bookings:
        if row.parent in names:
            continue
        doc = frappe.get_doc("Crane Assignment", row.parent)
        if company and doc.company and doc.company != company:
            continue
        doc.check_permission("read")
        names.add(doc.name)
        assignments.append(dict(name=doc.name, start=str(row.start_date), end=str(row.expected_end_date),
            label=f"{doc.name} · {doc.customer} · {doc.location}"))
    sheets = []
    if names:
        for row in frappe.get_all("Crane Timesheet", filters={"crane": crane,
                "assignment": ["in", sorted(names)], "docstatus": ["<", 2],
                "period_start": ["<=", end], "period_end": [">=", start]},
                fields=["name", "assignment", "period_start", "period_end", "docstatus"],
                order_by="period_start, name"):
            frappe.get_doc("Crane Timesheet", row.name).check_permission("read")
            sheets.append(dict(name=row.name, assignment=row.assignment,
                start=str(row.period_start), end=str(row.period_end),
                label=f"{row.name} · {row.assignment} · {row.period_start} → {row.period_end}"))
    return dict(assignments=assignments, timesheets=sheets)


def validate_context(doc):
    if not doc.get("crane"):
        if doc.get("crane_timesheet"):
            frappe.throw(_("Choose the Crane before selecting rental work."))
        return
    before = doc.get_doc_before_save()
    fields = ("docstatus", "company", "crane", "crane_assignment", "crane_timesheet", "posting_date", "service_from_date", "service_to_date") if doc.doctype == "Expense Entry" else (
        "status", "crane", "crane_assignment", "crane_timesheet", "actual_start_date", "actual_end_date")
    if before and all(str(doc.get(f) or "") == str(before.get(f) or "") for f in fields):
        return
    from heavy_equipment_rental.rental_validation import lock_cranes
    lock_cranes([doc.crane])
    if not doc.get("crane_assignment") and not doc.get("crane_timesheet"):
        return
    if doc.get("crane_timesheet"):
        sheet = frappe.get_doc("Crane Timesheet", doc.crane_timesheet)
        sheet.check_permission("read")
        if sheet.docstatus == 2 or sheet.crane != doc.crane:
            frappe.throw(_("Select a non-cancelled Timesheet for this Crane."))
        if doc.get("crane_assignment") and doc.crane_assignment != sheet.assignment:
            frappe.throw(_("Timesheet and Assignment must belong to the same rental job."))
        doc.crane_assignment = sheet.assignment
        if doc.doctype == "Expense Entry" and not doc.get("service_from_date"):
            doc.service_from_date, doc.service_to_date = sheet.period_start, sheet.period_end
    if doc.doctype == "Expense Entry" and doc.get("crane_assignment") and not doc.get("service_from_date"):
        from heavy_equipment_rental.rental_expenses import work_window
        doc.service_from_date, doc.service_to_date = work_window(doc)
    if doc.doctype == "Expense Entry" and doc.get("crane_timesheet"):
        if (getdate(doc.service_from_date) < getdate(sheet.period_start) or
                getdate(doc.service_to_date) > getdate(sheet.period_end)):
            frappe.throw(_("Expense service dates must fit the selected Timesheet."))
    start, end = window(doc)
    if start > end:
        frappe.throw(_("The work period end cannot precede its start."))
    options = rental_work_options(doc.crane, start, end, doc.get("company"))
    if doc.get("crane_assignment"):
        assignment = frappe.get_doc("Crane Assignment", doc.crane_assignment)
        assignment.check_permission("read")
        if doc.get("company") and assignment.company and assignment.company != doc.company:
            frappe.throw(_("Expense and Assignment must belong to the same Company."))
        if doc.crane_assignment not in {r["name"] for r in options["assignments"]}:
            frappe.throw(_("Select an Assignment matching this Crane and work period."))
        if doc.get("crane_timesheet") and doc.crane_timesheet not in {r["name"] for r in options["timesheets"]}:
            frappe.throw(_("Select a Timesheet matching this work period."))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def context_link_query(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else filters or {})
    if not filters.crane:
        return []
    options = rental_work_options(filters.crane, filters.get("from_date"), filters.get("to_date"), filters.get("company"))
    rows = options["assignments"] if doctype == "Crane Assignment" else options["timesheets"] if doctype == "Crane Timesheet" else []
    rows = [r for r in rows if (not filters.get("assignment") or r.get("assignment", r["name"]) == filters.assignment)
            and txt.lower() in (r["name"] + " " + r["label"]).lower()]
    return [(r["name"], r["label"]) for r in rows[start:start + page_len]]
