"""Confirmed, atomic cancellation of a rental document and its dependencies."""

import frappe
from frappe import _
from frappe.desk.form.linked_with import SubmittableDocumentTree

ROOTS = ("Sales Invoice", "Crane Timesheet", "Crane Profit Settlement")


def cancellation_plan(doctype, name):
    if doctype not in ROOTS:
        frappe.throw(_("Unsupported rental document."))
    pending = [(doctype, name)]
    seen = set()
    docs = []
    while pending:
        dt, dn = pending.pop(0)
        if (dt, dn) in seen:
            continue
        seen.add((dt, dn))
        doc = frappe.get_doc(dt, dn)
        doc.check_permission("read")
        if doc.docstatus != 1:
            continue
        docs.append(dict(doctype=dt, name=dn))
        # Follow business dependencies only. A Timesheet's invoice/settlement
        # references are historical backlinks, not children of those documents.
        if dt in ("Sales Invoice", "Purchase Invoice", "Crane Timesheet"):
            children = SubmittableDocumentTree(dt, dn).get_next_level_children(dt, [dn])
            pending.extend(("Crane Profit Settlement", child)
                           for child in children.get("Crane Profit Settlement", []))
        if dt == "Crane Timesheet":
            pending.extend((target, doc.get(field)) for field, target in (
                ("sales_invoice", "Sales Invoice"), ("purchase_invoice", "Purchase Invoice"),
                ("profit_settlement", "Crane Profit Settlement")) if doc.get(field))
        elif dt == "Crane Profit Settlement" and doc.journal_entry:
            pending.append(("Journal Entry", doc.journal_entry))
    # Settlement controllers reverse their journals. Existing payment and closed
    # period guards still apply; upstream work is never cancelled implicitly.
    priority = {"Payment Entry": 0, "Crane Profit Settlement": 1,
                "Sales Invoice": 2, "Purchase Invoice": 2, "Crane Timesheet": 3, "Journal Entry": 4}
    return sorted(docs, key=lambda row: (priority.get(row["doctype"], 0), row["name"]), reverse=False)


@frappe.whitelist()
def get_plan(doctype, name):
    return cancellation_plan(doctype, name)


@frappe.whitelist(methods=["POST"])
def cancel_all(doctype, name, confirmed_plan):
    plan = cancellation_plan(doctype, name)
    expected = frappe.parse_json(confirmed_plan)
    if plan != expected:
        frappe.throw(_("Linked documents changed. Review and confirm cancellation again."))
    for row in plan:
        frappe.get_doc(row["doctype"], row["name"]).check_permission("cancel")
    frappe.db.savepoint("rental_cancel_all")
    try:
        for row in plan:
            doc = frappe.get_doc(row["doctype"], row["name"])
            if doc.docstatus == 1:
                doc.cancel()
    except Exception:
        frappe.db.rollback(save_point="rental_cancel_all")
        raise
    return plan
