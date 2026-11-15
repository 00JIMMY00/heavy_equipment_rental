"""Dependency preview for native Maintenance cancellation; no upstream purchases."""
import frappe
from frappe import _
from frappe.utils import get_datetime


def build_plan(name):
    job = frappe.get_doc('Crane Maintenance', name, for_update=True)
    job.check_permission('read')
    from heavy_equipment_rental.rental_validation import lock_cranes
    lock_cranes([job.crane])
    from heavy_equipment_rental.crane_repairs import documents
    rows = documents(name)
    for expense in frappe.get_all('Expense Entry', filters={'crane_maintenance': name}, fields=['name', 'docstatus']):
        rows.append(dict(doctype='Expense Entry', **expense))
    for field, dt in [('repair_purchase_invoice', 'Purchase Invoice'), ('repair_material_issue', 'Stock Entry'), ('expense_entry', 'Expense Entry')]:
        if job.get(field):
            linked = frappe.get_doc(dt, job.get(field))
            linked.check_permission('read')
            if linked.get('crane_maintenance') != name:
                frappe.throw(_('Linked document {0} does not belong to this Maintenance.').format(linked.name))
    if any(row['docstatus'] == 0 for row in rows):
        frappe.throw(_('Delete draft repair documents before cancelling Maintenance. Drafts have no accounting to reverse.'))
    pending = [(row['doctype'], row['name']) for row in rows if row['docstatus'] == 1]
    if job.repair_payment_entry:
        pending.append(('Payment Entry', job.repair_payment_entry))
    seen, result, asset_order = set(), [], {}
    while pending:
        dt, dn = pending.pop(0)
        if (dt, dn) in seen:
            continue
        seen.add((dt, dn))
        doc = frappe.get_doc(dt, dn)
        doc.check_permission('read')
        if doc.docstatus != 1:
            continue
        result.append(dict(doctype=dt, name=dn))
        if dt == 'Asset Repair':
            asset_order[dn] = -get_datetime(doc.creation).timestamp()
        if dt == 'Expense Entry' and doc.journal_entry:
            pending.append(('Journal Entry', doc.journal_entry))
        if dt in ('Purchase Invoice', 'Sales Invoice', 'Journal Entry'):
            payments = frappe.get_all('Payment Entry', filters=[
                ['Payment Entry', 'docstatus', '=', 1],
                ['Payment Entry Reference', 'reference_doctype', '=', dt],
                ['Payment Entry Reference', 'reference_name', '=', dn]], pluck='name', distinct=True)
            pending.extend(('Payment Entry', n) for n in payments)
            for entry in frappe.get_all('Payment Ledger Entry', filters={
                'against_voucher_type': dt, 'against_voucher_no': dn,
                'voucher_no': ['!=', dn], 'delinked': 0}, fields=['voucher_type', 'voucher_no']):
                if entry.voucher_type != 'Payment Entry':
                    frappe.throw(_('Unreconcile adjustment {0} before cancelling Maintenance.').format(entry.voucher_no))
                pending.append(('Payment Entry', entry.voucher_no))
    targets = {(r['doctype'], r['name']) for r in result}
    for row in result:
        if row['doctype'] == 'Payment Entry':
            payment = frappe.get_doc('Payment Entry', row['name'])
            if any(r.allocated_amount and (r.reference_doctype, r.reference_name) not in targets for r in payment.references):
                frappe.throw(_('Payment {0} also pays documents outside this repair. Cancel or unreconcile that payment separately first.').format(payment.name))
    priority = {'Payment Entry': 0, 'Asset Repair': 1, 'Stock Entry': 2,
        'Sales Invoice': 3, 'Purchase Invoice': 3, 'Expense Entry': 3, 'Journal Entry': 4}
    result.sort(key=lambda row: (priority[row['doctype']], asset_order.get(row['name'], 0) if row['doctype'] == 'Asset Repair' else 0, row['name']))
    result.append(dict(doctype='Crane Maintenance', name=name))
    return result


@frappe.whitelist()
def get_plan(name):
    return build_plan(name)


@frappe.whitelist(methods=['POST'])
def cancel_with_plan(name, confirmed_plan):
    job = frappe.get_doc('Crane Maintenance', name, for_update=True)
    job.check_permission('cancel')
    if job.docstatus != 1:
        frappe.throw(_('Only submitted Maintenance can be cancelled.'))
    if build_plan(name) != frappe.parse_json(confirmed_plan):
        frappe.throw(_('Linked documents changed. Review cancellation again.'))
    job.cancel()
    return name
