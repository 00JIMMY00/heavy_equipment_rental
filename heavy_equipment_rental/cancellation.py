"""Confirmed, atomic cancellation of a rental document and its dependencies."""

import frappe
from frappe.utils import getdate
from frappe import _
from frappe.desk.form.linked_with import SubmittableDocumentTree

ROOTS = ("Sales Invoice", "Crane Timesheet", "Crane Profit Settlement", "Expense Entry")


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
        if dt == "Expense Entry":
            from heavy_equipment_rental.rental_expenses import affected_settlements
            pending.extend(("Crane Profit Settlement", n) for n in affected_settlements(doc))
            if doc.journal_entry:
                pending.append(("Journal Entry", doc.journal_entry))
        if dt in ("Sales Invoice", "Purchase Invoice", "Journal Entry"):
            # Include complete native payments, even those allocated to several documents.
            payments = frappe.get_all("Payment Entry", filters=[
                ["Payment Entry", "docstatus", "=", 1],
                ["Payment Entry Reference", "reference_doctype", "=", dt],
                ["Payment Entry Reference", "reference_name", "=", dn]], pluck="name", distinct=True)
            pending.extend(("Payment Entry", n) for n in payments)
            for movement in frappe.get_all("Payment Ledger Entry", filters={
                    "against_voucher_type": dt, "against_voucher_no": dn,
                    "voucher_no": ["!=", dn], "delinked": 0}, fields=["voucher_type", "voucher_no"]):
                if movement.voucher_type == "Payment Entry":
                    pending.append(("Payment Entry", movement.voucher_no))
                else:
                    adjustment = frappe.get_doc(movement.voucher_type, movement.voucher_no)
                    adjustment.check_permission("read")
                    frappe.throw(_("Unreconcile adjustment {0} before cancelling.").format(adjustment.name))
        if dt == "Crane Timesheet":
            pending.extend((target, doc.get(field)) for field, target in (
                ("sales_invoice", "Sales Invoice"), ("purchase_invoice", "Purchase Invoice"),
                ("profit_settlement", "Crane Profit Settlement")) if doc.get(field))
        elif dt == "Crane Profit Settlement":
            if doc.settlement_basis != "Timesheet":
                pending.extend((dt, n) for n in frappe.get_all(dt, filters={"crane": doc.crane,
                    "docstatus": 1, "to_date": [">", doc.to_date]}, pluck="name"))
            if doc.journal_entry:
                pending.append(("Journal Entry", doc.journal_entry))
    priority = {"Payment Entry": 0, "Crane Profit Settlement": 1,
                "Sales Invoice": 2, "Purchase Invoice": 2, "Expense Entry": 2,
                "Crane Timesheet": 3, "Journal Entry": 4}
    def order(row):
        # Period settlements must reverse newest first.
        end = frappe.db.get_value(row["doctype"], row["name"], "to_date") if row["doctype"] == "Crane Profit Settlement" else None
        return (priority[row["doctype"]], -getdate(end).toordinal() if end else 0, row["name"])
    return sorted(docs, key=order)


@frappe.whitelist()
def get_plan(doctype, name):
    return cancellation_plan(doctype, name)


@frappe.whitelist(methods=["POST"])
def cancel_all(doctype, name, confirmed_plan):
    from heavy_equipment_rental.rental_validation import lock_cranes
    root = frappe.get_doc(doctype, name)
    root.check_permission("read")
    cranes = [root.get("crane")]
    if doctype == "Sales Invoice":
        from heavy_equipment_rental.profit_sharing import source_cranes
        cranes.extend(source_cranes(root))
    lock_cranes(cranes)
    plan = cancellation_plan(doctype, name)
    # Serialize against new allocations while revalidating the confirmation.
    for row in plan:
        if row["doctype"] == "Journal Entry":
            frappe.get_doc("Journal Entry", row["name"], for_update=True)
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
