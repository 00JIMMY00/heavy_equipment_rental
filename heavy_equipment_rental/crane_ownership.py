"""Derive ownership independently from supplier hire and operating fees."""
import frappe
from frappe import _
from frappe.utils import flt


def validate_ownership(doc):
    if doc.enable_profit_sharing and doc.hired_from_supplier:
        frappe.throw(_("Choose either Enable Profit Sharing or Hired from Supplier, not both."))
    before = doc.get_doc_before_save()
    if doc.is_new() and not doc.ownership_partners and not doc.hired_from_supplier and doc.ownership_type == 'Owned':
        doc.append('ownership_partners', dict(is_company=1, ownership_percentage=100, profit_percentage=100))
    from heavy_equipment_rental.profit_sharing import percentage
    rows = doc.ownership_partners
    if not rows and not doc.hired_from_supplier:
        frappe.throw(_("Enter the crane's owners, or select Hired from Supplier."))
    if doc.hired_from_supplier and not doc.supplier:
        frappe.throw(_("Select the rental Supplier."))
    if doc.hired_from_supplier:
        doc.ownership_classification = "Hired from Supplier"
        doc.ownership_type = "Rented"
        return
    if rows:
        if abs(sum(flt(r.ownership_percentage) for r in rows) - 100) > 0.000001:
            frappe.throw(_("Ownership percentages must total 100%."))
        seen = set()
        for row in rows:
            row.ownership_percentage = percentage(row.ownership_percentage)
            if not row.is_company and row.shareholder:
                owner = frappe.get_doc("Shareholder", row.shareholder)
                owner.check_permission("read")
                if not doc.sharing_company or owner.company != doc.sharing_company:
                    frappe.throw(_("Select the Company matching the owner Shareholders."))
            key = 'company' if row.is_company else row.shareholder
            if not key or key in seen:
                frappe.throw(_("Select each owner once using Our Company or a Shareholder."))
            seen.add(key)
            if not 0 <= flt(row.ownership_percentage) <= 100:
                frappe.throw(_("Ownership percentages must be between 0 and 100."))
    share = sum(flt(r.ownership_percentage) for r in rows if r.is_company)
    doc.ownership_classification = ('Ownership Not Recorded' if not rows else
        'Company Owned' if share == 100 else 'Shared Ownership' if share else 'Externally Owned')
    # Keep the historical field as an internal compatibility value.
    if before and [(r.is_company, r.shareholder, r.ownership_percentage) for r in rows] == [(r.is_company, r.shareholder, r.ownership_percentage) for r in before.ownership_partners]:
        doc.ownership_type = before.ownership_type
        return
    doc.ownership_type = 'Owned' if share == 100 else 'Shared Ownership' if share else 'Other'


@frappe.whitelist()
def list_ownership(cranes):
    """Return owner shares only for cranes visible under normal list permissions."""
    names = frappe.parse_json(cranes)
    if not isinstance(names, list) or len(names) > 500:
        frappe.throw(_("Invalid crane selection."))
    visible = frappe.get_list("Crane", filters={"name": ["in", names]}, pluck="name", limit_page_length=500)
    result = {name: [] for name in visible}
    if not visible:
        return result
    for row in frappe.get_all("Crane Partner", filters={"parent": ["in", visible], "parenttype": "Crane", "parentfield": "ownership_partners"},
                             fields=["parent", "is_company", "shareholder", "ownership_percentage"], order_by="idx"):
        result[row.parent].append(row)
    return result
