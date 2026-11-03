"""Supplier invoices and native ERPNext payments for rented cranes."""

from calendar import monthrange
from decimal import Decimal

import erpnext
import frappe
from frappe import _
from frappe.utils import flt, today

from heavy_equipment_rental.rental_validation import interval, work_days


def purchase_work_quantity(sheet):
    """Use actual work, independent of idle dates and customer billing terms."""
    hours = flt(sheet.total_crane_billable_hours, sheet.precision("total_crane_billable_hours"))
    if sheet.purchase_uom == "Hour":
        return hours, 1
    if sheet.purchase_uom not in ("Day", "Month"):
        frappe.throw(_("Select an Hour, Day or Month Supplier Billing UOM."))
    days = {day for row in sheet.timesheet_entries for day in work_days(*interval(row))}
    quantity = len(days) if sheet.purchase_uom == "Day" else float(sum(
        (Decimal(1) / Decimal(monthrange(day.year, day.month)[1]) for day in days), Decimal(0)))
    return quantity, hours / quantity if quantity else 1


def create_purchase_invoice(sheet):
    """Called only by Timesheet submission, inside the same transaction."""
    existing = frappe.db.get_value("Crane Timesheet", sheet.name, "purchase_invoice")
    if existing:
        return existing
    if sheet.crane_ownership_type != "Rented" or not sheet.rented:
        return None
    quantity, conversion_factor = purchase_work_quantity(sheet)
    if quantity <= 0 or flt(sheet.purchase_rate) <= 0:
        frappe.throw(_("Rented Timesheets require positive recorded work and a positive Purchase Price per Unit."))
    company = frappe.db.get_value("Crane Assignment", sheet.assignment, "company") or erpnext.get_default_company()
    if not company:
        frappe.throw(_("Set a Company on the Assignment or a default Company."))
    crane = frappe.get_doc("Crane", sheet.crane)
    item = frappe.get_doc("Item", crane.item)
    if item.disabled or item.is_stock_item or not item.is_purchase_item or item.stock_uom != "Hour":
        frappe.throw(_("The Crane Item must be an enabled, non-stock Hour service with Allow Purchase enabled."))
    currency = frappe.get_cached_value("Company", company, "default_currency")
    invoice = frappe.get_doc({
        "doctype": "Purchase Invoice", "company": company, "supplier": sheet.purchase_supplier,
        "currency": currency, "conversion_rate": 1,
        "posting_date": today(), "due_date": today(), "update_stock": 0,
        "remarks": _("Crane Timesheet {0}; Assignment {1}; service period {2} to {3}").format(
            sheet.name, sheet.assignment, sheet.period_start, sheet.period_end),
        "items": [{
            "item_code": item.name, "uom": sheet.purchase_uom, "conversion_factor": conversion_factor,
            "qty": quantity, "rate": sheet.purchase_rate,
            "description": _("Crane {0}; Timesheet {1}; {2} to {3}; {4} {5} at {6} per {5}").format(
                crane.crane_name, sheet.name, sheet.period_start, sheet.period_end,
                quantity, sheet.purchase_uom, sheet.purchase_rate),
        }],
    })
    invoice.insert()
    invoice.submit()
    sheet.db_set("purchase_invoice", invoice.name, update_modified=False)
    return invoice.name


def allow_timesheet_invoice_cancel(invoice, method=None):
    # Keep the historical link while allowing invoice-first cancellation.
    invoice.ignore_linked_doctypes = tuple(invoice.get("ignore_linked_doctypes") or ()) + ("Crane Timesheet",)


@frappe.whitelist()
def supplier_payment_invoices(source_doctype, source_name):
    if source_doctype not in ("Crane", "Crane Timesheet"):
        frappe.throw(_("Choose a Crane or Crane Timesheet."))
    source = frappe.get_doc(source_doctype, source_name)
    source.check_permission("read")
    frappe.has_permission("Payment Entry", "create", throw=True)
    filters = {"crane": source_name} if source_doctype == "Crane" else {"name": source_name}
    filters.update({"docstatus": 1, "purchase_invoice": ["is", "set"]})
    invoices = frappe.get_list("Crane Timesheet", filters=filters, pluck="purchase_invoice", limit_page_length=0)
    if not invoices:
        return []
    return frappe.get_list("Purchase Invoice", filters={
        "name": ["in", invoices], "docstatus": 1, "outstanding_amount": [">", 0],
    }, fields=["name", "supplier", "outstanding_amount", "currency"],
        order_by="posting_date asc, name asc", limit_page_length=0)


@frappe.whitelist()
def make_supplier_payment(source_doctype, source_name, purchase_invoice):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    invoices = supplier_payment_invoices(source_doctype, source_name)
    if purchase_invoice not in {row.name for row in invoices}:
        frappe.throw(_("Choose an unpaid submitted Purchase Invoice linked to this record."))
    # ERPNext supplies the supplier, company, outstanding amount and invoice reference.
    # Return an unsaved Payment Entry so the user can choose bank and payment details.
    return get_payment_entry("Purchase Invoice", purchase_invoice)
