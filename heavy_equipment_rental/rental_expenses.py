"""Attribute posted expenses to rental work independently of accounting dates."""

import frappe
from frappe import _
from frappe.utils import getdate, flt


def work_window(expense):
    if expense.get("doctype") == "Expense Entry":
        return getdate(expense.posting_date), getdate(expense.posting_date)
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
            frappe.throw(_("The Crane must belong to the selected Rental Contract."))
        return min(getdate(r.start_date) for r in rows), max(getdate(r.expected_end_date) for r in rows)
    return getdate(expense.posting_date), getdate(expense.posting_date)


def validate_expense(expense):
    from heavy_equipment_rental.rental_context import validate_context
    validate_context(expense)
    if expense.get("crane_assignment"):
        assignment = frappe.get_doc("Rental Contract", expense.crane_assignment)
        assignment.check_permission("read")
        if assignment.company and assignment.company != expense.company:
            frappe.throw(_("Expense and Rental Contract must belong to the same Company."))
        cranes = {r.crane for r in assignment.assigned_cranes if not r.cancelled}
        if not expense.crane and len(cranes) == 1:
            expense.crane = next(iter(cranes))
        if expense.crane not in cranes:
            frappe.throw(_("Select a Crane from the selected Rental Contract."))


def matches(source, sheet):
    # Explicit work links are authoritative; dates never select the charged job.
    if source.get("rental_timesheet"):
        return source["rental_timesheet"] == sheet.name and (
            not source.get("rental_assignment") or source["rental_assignment"] == sheet.assignment)
    return bool(source.get("rental_assignment")) and source["rental_assignment"] == sheet.assignment


def expense_sources(crane, company):
    from heavy_equipment_rental.consolidated_accounting import sources
    yield from sources(crane, company)
    for name in frappe.get_all("Expense Entry", filters={"crane": crane, "company": company,
            "docstatus": 1}, pluck="name"):
        expense = frappe.get_doc("Expense Entry", name)
        if not expense.crane_assignment and not expense.get("crane_timesheet"):
            continue
        start, end = work_window(expense)
        yield expense, dict(doctype="Expense Entry", name=name, journal=expense.journal_entry,
            posting_date=str(expense.posting_date), rental_assignment=expense.crane_assignment,
            rental_timesheet=expense.get("crane_timesheet"),
            service_from_date=str(start), service_to_date=str(end),
            basis="Selected Timesheet" if expense.get("crane_timesheet") else "Selected Rental Contract / worked hours",
            expenses=sum(flt(r.amount) for r in expense.expenses))


def check_posted(expense):
    expense.check_permission("read")
    journal = expense if expense.doctype == "Journal Entry" else (frappe.get_doc("Journal Entry", expense.journal_entry) if expense.journal_entry else None)
    if not journal or journal.docstatus != 1 or journal.company != expense.company:
        frappe.throw(_("Expense {0} has no valid posted Journal Entry; resolve it before settlement.").format(expense.name))
    journal.check_permission("read")


def guard_expense(expense):
    if not expense.crane:
        return
    if expense.get("doctype") == "Expense Entry":
        # Also protect direct cancellation of the expense's generated journal.
        from heavy_equipment_rental.timesheet_settlement import guard_source_snapshots
        guard_source_snapshots(expense, [expense.crane])
    agreement_company, history = frappe.db.get_value("Crane", expense.crane, ["sharing_company", "agreement_history"])
    if history and agreement_company and agreement_company != expense.company:
        frappe.throw(_("Crane {0} belongs to another agreement Company.").format(expense.crane))
    if not expense.get("crane_assignment") and not expense.get("crane_timesheet"):
        return
    start, end = work_window(expense)
    for row in frappe.get_all("Crane Profit Settlement", filters={"crane": expense.crane,
            "company": expense.company, "docstatus": 1},
            fields=["name", "timesheet", "settlement_basis", "from_date", "to_date"]):
        if settlement_matches(expense, row, start, end):
            frappe.throw(_("Work expenses are closed by settlement {0}. Cancel the affected settlement before posting or cancelling this expense.").format(row.name))


def settlement_matches(expense, settlement, start, end):
    if not expense.get("crane_assignment") and not expense.get("crane_timesheet"):
        return False
    if settlement.settlement_basis == "Timesheet":
        sheet = frappe._dict(name=settlement.timesheet, assignment=frappe.db.get_value(
            "Crane Timesheet", settlement.timesheet, "assignment"))
        return matches(dict(rental_timesheet=expense.get("crane_timesheet"),
            rental_assignment=expense.get("crane_assignment")), sheet)
    # Legacy period closures still split explicitly linked costs by service period.
    return getdate(settlement.from_date) <= end and getdate(settlement.to_date) >= start


def affected_settlements(expense):
    """Submitted closures whose snapshots or work windows protect this expense."""
    import json

    if not expense.crane:
        return []
    start, end = work_window(expense)
    result = []
    for row in frappe.get_all("Crane Profit Settlement", filters={"crane": expense.crane,
            "company": expense.company, "docstatus": 1},
            fields=["name", "from_date", "to_date", "timesheet", "settlement_basis", "source_snapshot"]):
        captured = any(s["doctype"] == expense.doctype and s["name"] == expense.name
                       for s in json.loads(row.source_snapshot or "[]"))
        overlaps = settlement_matches(expense, row, start, end)
        if captured or overlaps:
            result.append(row.name)
    return result


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def assignment_cranes(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else filters or {})
    if not filters.assignment:
        return []
    assignment = frappe.get_doc("Rental Contract", filters.assignment)
    assignment.check_permission("read")
    names = list({r.crane for r in assignment.assigned_cranes if not r.cancelled and r.crane})
    if not names:
        return []
    return frappe.get_list("Crane", filters={"name": ["in", names]},
        or_filters={"name": ["like", "%" + txt + "%"], "crane_name": ["like", "%" + txt + "%"]},
        fields=["name", "crane_name"], order_by="crane_name, name", start=start, page_length=page_len, as_list=True)
