"""Explicit fee recipients and bases; historical single-operator compatibility."""
import frappe
from frappe import _
from frappe.utils import flt


def agreement_rows(agreement):
    if 'operating_fees' in agreement:
        return agreement['operating_fees']
    return [dict(is_company=int(agreement.get('operator_type', 'Our Company') == 'Our Company'),
        shareholder=agreement.get('operating_shareholder'), basis='Legacy Revenue',
        percentage=flt(agreement.get('operating_percentage')))]


def canonical_rows(rows):
    return sorted([dict(is_company=int(bool(r.get('is_company'))),
        shareholder=None if r.get('is_company') else r.get('shareholder'),
        basis=r.get('basis'), percentage=flt(r.get('percentage'))) for r in rows],
        key=lambda r:(r['is_company'], r['shareholder'] or '', r['basis']))


def validate_rows(doc):
    from heavy_equipment_rental.profit_sharing import percentage
    if not doc.operating_fees:
        doc.append('operating_fees', dict(is_company=1,basis='Grand Total',percentage=0))
    seen=set()
    for row in doc.operating_fees:
        row.percentage=percentage(row.percentage)
        if row.basis not in ('Grand Total','Net Profit'):
            frappe.throw(_('Choose Grand Total or Net Profit for each operating fee.'))
        if row.is_company:
            row.shareholder=None
        else:
            if not row.shareholder:
                frappe.throw(_('Select the operating fee Partner.'))
            partner=frappe.get_doc('Shareholder',row.shareholder)
            partner.check_permission('read')
            if partner.company != doc.sharing_company:
                frappe.throw(_('Operating fee Partners must belong to the Crane Company.'))
        key=('company' if row.is_company else row.shareholder,row.basis)
        if key in seen:
            frappe.throw(_('Enter each operating recipient once per fee basis.'))
        seen.add(key)
    if sum(r.percentage for r in doc.operating_fees)>100:
        frappe.throw(_('Combined operating fee percentages cannot exceed 100%.'))
    if any(r.percentage for r in doc.operating_fees) and not doc.enable_profit_sharing:
        frappe.throw(_('Enable Profit Sharing to apply operating fees.'))
    return canonical_rows(doc.operating_fees)


def calculate(agreement, revenue, expenses, precision):
    result=[]
    for row in agreement_rows(agreement):
        base=max(revenue-expenses,0) if row['basis']=='Net Profit' else revenue
        result.append(dict(row,base=base,amount=flt(base*flt(row['percentage'])/100,precision)))
    return result
