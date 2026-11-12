"""Attribute posted expenses to rental work independently of accounting dates."""

import frappe
from frappe import _
from frappe.utils import getdate, flt


def work_window(expense):
    start, end = expense.get("service_from_date"), expense.get("service_to_date")
    if bool(start) != bool(end):
        frappe.throw(_("Enter both Service From Date and Service To Date."))
    if start:
        if getdate(start) > getdate(end):
            frappe.throw(_("Service To Date must be on or after Service From Date."))
        return getdate(start), getdate(end)
    if expense.get("crane_assignment"):
        rows = frappe.get_all("Assigned Crane", filters={"parent": expense.crane_assignment,
            "crane": expense.crane, "cancelled": 0}, fields=["start_date", "expected_end_date"])
        if not rows:
            frappe.throw(_("The Crane must belong to the selected Assignment."))
        return min(getdate(r.start_date) for r in rows), max(getdate(r.expected_end_date) for r in rows)
    return getdate(expense.posting_date), getdate(expense.posting_date)


def validate_expense(expense):
    if expense.get("crane_assignment"):
        assignment = frappe.get_doc("Crane Assignment", expense.crane_assignment)
        assignment.check_permission("read")
        if assignment.company and assignment.company != expense.company:
            frappe.throw(_("Expense and Assignment must belong to the same Company."))
        cranes = {r.crane for r in assignment.assigned_cranes if not r.cancelled}
        if not expense.crane and len(cranes) == 1:
            expense.crane = next(iter(cranes))
        if expense.crane not in cranes:
            frappe.throw(_("Select a Crane from the selected Assignment."))
    if not expense.crane:
        if expense.get("service_from_date") or expense.get("service_to_date"):
            frappe.throw(_("Select a Crane before entering service dates."))
        return
    start, end = work_window(expense)
    if expense.get("crane_assignment"):
        rows = frappe.get_all("Assigned Crane", filters={"parent": expense.crane_assignment,
            "crane": expense.crane, "cancelled": 0}, fields=["start_date", "expected_end_date"])
        # Check the entire interval, including gaps between separate bookings.
        from frappe.utils import add_days
        day = start
        while day <= end:
            if not any(getdate(r.start_date) <= day <= getdate(r.expected_end_date) for r in rows):
                frappe.throw(_("Expense service dates must fit the Crane's Assignment booking."))
            day = getdate(add_days(day, 1))
    if expense.docstatus == 0 and expense.get("crane_assignment") and not expense.get("service_from_date"):
        expense.service_from_date, expense.service_to_date = start, end


def matches(source, sheet):
    return (not source.get("rental_assignment") or source["rental_assignment"] == sheet.assignment) and (
        getdate(sheet.period_start) <= getdate(source["service_to_date"]) and
        getdate(sheet.period_end) >= getdate(source["service_from_date"]))


def expense_sources(crane, company):
    for name in frappe.get_all("Expense Entry", filters={"crane": crane, "company": company,
            "docstatus": 1}, pluck="name"):
        expense = frappe.get_doc("Expense Entry", name)
        start, end = work_window(expense)
        yield expense, dict(doctype="Expense Entry", name=name, journal=expense.journal_entry,
            posting_date=str(expense.posting_date), rental_assignment=expense.crane_assignment,
            service_from_date=str(start), service_to_date=str(end),
            basis="Assignment / service period" if expense.crane_assignment or expense.get("service_from_date") else "Posting date",
            expenses=sum(flt(r.amount) for r in expense.expenses))


def check_posted(expense):
    expense.check_permission("read")
    journal = frappe.get_doc("Journal Entry", expense.journal_entry) if expense.journal_entry else None
    if not journal or journal.docstatus != 1 or journal.company != expense.company:
        frappe.throw(_("Expense {0} has no valid posted Journal Entry; resolve it before settlement.").format(expense.name))
    journal.check_permission("read")


def guard_expense(expense):
    if not expense.crane:
        return
    agreement_company, history = frappe.db.get_value("Crane", expense.crane, ["sharing_company", "agreement_history"])
    if history and agreement_company and agreement_company != expense.company:
        frappe.throw(_("Crane {0} belongs to another agreement Company.").format(expense.crane))
    start, end = work_window(expense)
    for row in frappe.get_all("Crane Profit Settlement", filters={"crane": expense.crane,
            "company": expense.company, "docstatus": 1, "from_date": ["<=", end],
            "to_date": [">=", start]}, fields=["name", "timesheet", "settlement_basis"]):
        if row.settlement_basis == "Timesheet" and expense.crane_assignment:
            if frappe.db.get_value("Crane Timesheet", row.timesheet, "assignment") != expense.crane_assignment:
                continue
        frappe.throw(_("Work expenses are closed by settlement {0}. Cancel the affected settlement before posting or cancelling this expense.").format(row.name))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def assignment_cranes(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else filters or {})
    if not filters.assignment:
        return []
    assignment = frappe.get_doc("Crane Assignment", filters.assignment)
    assignment.check_permission("read")
    names = list({r.crane for r in assignment.assigned_cranes if not r.cancelled and r.crane})
    if not names:
        return []
    return frappe.get_list("Crane", filters={"name": ["in", names]},
        or_filters={"name": ["like", "%" + txt + "%"], "crane_name": ["like", "%" + txt + "%"]},
        fields=["name", "crane_name"], order_by="crane_name, name", start=start, page_length=page_len, as_list=True)
