"""Payment-mode funding accounts, counted once, from posted native GL movements."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not all(filters.get(key) for key in ('company', 'from_date', 'to_date')):
        frappe.throw(_('Company, From Date and To Date are required.'))
    first, last = getdate(filters.from_date), getdate(filters.to_date)
    if first > last:
        frappe.throw(_('From Date must be before To Date.'))
    frappe.has_permission('GL Entry', 'read', throw=True)
    frappe.has_permission('Mode of Payment', 'read', throw=True)
    company = frappe.get_doc('Company', filters.company)
    company.check_permission('read')
    if filters.mode_of_payment:
        frappe.get_doc('Mode of Payment', filters.mode_of_payment).check_permission('read')

    accounts = payment_accounts(filters)
    ledger = frappe.get_list('GL Entry', filters={
        'company': filters.company, 'account': ['in', list(accounts)],
        'is_cancelled': 0, 'posting_date': ['<=', last],
    }, fields=['name', 'account', 'posting_date', 'voucher_type', 'voucher_no',
               'debit', 'credit', 'remarks'], order_by='posting_date, creation, name',
        limit_page_length=0) if accounts else []
    sources = journal_sources(ledger, filters.company)
    documents = {}

    def document(doctype, name):
        key = (doctype, name)
        if key not in documents:
            doc = frappe.get_doc(doctype, name)
            doc.check_permission('read')
            if doc.docstatus != 1 or doc.get('company') != filters.company:
                frappe.throw(_('Document {0} has no valid submitted accounting source.').format(name))
            documents[key] = doc
        return documents[key]

    movements = defaultdict(dict)
    opening = defaultdict(float)
    for entry in ledger:
        voucher = document(entry.voucher_type, entry.voucher_no)
        source = voucher
        remarks = voucher.get('user_remark') or voucher.get('remarks') or entry.remarks or ''
        if entry.voucher_type == 'Journal Entry':
            for kind, name, description in sources.get(entry.voucher_no, []):
                source = document(kind, name)
                remarks = description or source.get('description') or remarks
        if getdate(entry.posting_date) < first:
            opening[entry.account] += flt(entry.debit) - flt(entry.credit)
            continue
        # One movement per account and voucher, even for split GL rows. Reading
        # only GL avoids counting an expense and its generated journal twice.
        key = (entry.voucher_type, entry.voucher_no)
        row = movements[entry.account].setdefault(key, dict(
            posting_date=entry.posting_date, incoming=0, outgoing=0,
            remarks=remarks, voucher_type=source.doctype, voucher=source.name,
        ))
        row['incoming'] += flt(entry.debit)
        row['outgoing'] += flt(entry.credit)

    currency = company.default_currency
    precision = frappe.get_precision('GL Entry', 'debit', currency=currency)
    data, totals = [], []
    for account, modes in sorted(accounts.items(), key=lambda item: item[1]):
        common = dict(account=account, payment_modes=' / '.join(modes), currency=currency)
        balance = flt(opening[account], precision)
        data.append(dict(common, posting_date=first, incoming=0, outgoing=0,
                         balance=balance, remarks=_('Opening Balance'), is_opening=1))
        incoming = outgoing = 0
        # The ledger query is chronological, with creation/name breaking ties.
        for row in movements[account].values():
            row['incoming'] = flt(row['incoming'], precision)
            row['outgoing'] = flt(row['outgoing'], precision)
            incoming += row['incoming']
            outgoing += row['outgoing']
            balance = flt(balance + row['incoming'] - row['outgoing'], precision)
            data.append(dict(common, **row, balance=balance))
        totals.append(dict(common, opening=flt(opening[account], precision),
                           incoming=flt(incoming, precision), outgoing=flt(outgoing, precision), balance=balance))

    message = _('Posted account movements in company currency. Balances run separately for each payment account. '
                'Modes sharing an account are shown together; selecting either mode shows the shared account. '
                'Transfers appear as OUT from the source and IN to the destination when both accounts are configured.')
    if not accounts:
        message = _('No payment accounts are configured for this Company.')
    summary = [dict(label=_(label), value=flt(sum(row[field] for row in totals), precision),
                    datatype='Currency', currency=currency)
               for field, label in (('opening', 'Opening Balance'), ('incoming', 'IN'),
                                    ('outgoing', 'OUT'), ('balance', 'Closing Balance'))]
    return columns(), data, message, payment_chart(totals, currency), summary, True


def payment_accounts(filters, *, account_names=None):
    """Include disabled modes/accounts for history; never duplicate account money."""
    accounts = defaultdict(list)
    selected_account = None
    for name in frappe.get_list('Mode of Payment', pluck='name', limit_page_length=0):
        mode = frappe.get_doc('Mode of Payment', name)
        mode.check_permission('read')
        for row in mode.accounts:
            if (row.company == filters.company and row.default_account
                    and (account_names is None or row.default_account in account_names)):
                accounts[row.default_account].append(name)
                if name == filters.mode_of_payment:
                    selected_account = row.default_account
    if filters.mode_of_payment:
        if not selected_account:
            frappe.throw(_('The selected Mode of Payment has no default account for this Company.'))
        accounts = {selected_account: accounts[selected_account]}
    for name, modes in accounts.items():
        account = frappe.get_doc('Account', name)
        account.check_permission('read')
        if account.company != filters.company or account.is_group:
            frappe.throw(_('Payment account {0} must be a ledger account in the selected Company.').format(name))
        accounts[name] = sorted(set(modes))
    return accounts


def journal_sources(ledger, company):
    """Resolve app sources for remarks and permission checks, including legacy batches."""
    journals = sorted({row.voucher_no for row in ledger if row.voucher_type == 'Journal Entry'})
    sources = defaultdict(list)
    if not journals:
        return sources
    expenses = {}
    for kind in ('Expense Entry', 'Treasury Transaction'):
        for row in frappe.get_all(kind, filters={'company': company, 'journal_entry': ['in', journals]},
                                  fields=['name', 'journal_entry']):
            sources[row.journal_entry].append((kind, row.name, None))
            if kind == 'Expense Entry':
                expenses[row.name] = row.journal_entry
    conditions = [['journal_entry', 'in', journals]]
    if expenses:
        conditions.append(['expense_entry', 'in', list(expenses)])
    for row in frappe.get_all('Grouped Expense Item', filters={'parenttype': 'Grouped Expense'},
                              or_filters=conditions,
                              fields=['parent', 'journal_entry', 'expense_entry', 'description']):
        journal = row.journal_entry or expenses.get(row.expense_entry)
        if journal:
            sources[journal].append(('Grouped Expense', row.parent, row.description))
    return sources


def payment_chart(totals, currency):
    return dict(type='bar', height=300, colors=['#249c68', '#d64b4b', '#4c78a8'],
                data=dict(labels=[row['payment_modes'] for row in totals], datasets=[
                    dict(name=f'{_(label)} ({currency})', values=[row[field] for row in totals])
                    for field, label in (('incoming', 'IN'), ('outgoing', 'OUT'), ('balance', 'Closing Balance'))
                ]), barOptions=dict(spaceRatio=0.35))


def columns():
    return [
        dict(fieldname='posting_date', label=_('Date'), fieldtype='Date', width=110),
        dict(fieldname='payment_modes', label=_('Mode of Payment'), fieldtype='Data', width=210),
        *[dict(fieldname=field, label=_(label), fieldtype='Currency', options='currency', width=135)
          for field, label in (('incoming', 'IN'), ('outgoing', 'OUT'), ('balance', 'Balance'))],
        dict(fieldname='remarks', label=_('Remarks'), fieldtype='Data', width=380),
        dict(fieldname='voucher', label=_('Document'), fieldtype='Dynamic Link', options='voucher_type', width=170),
        dict(fieldname='voucher_type', label=_('Document Type'), fieldtype='Data', hidden=1),
        dict(fieldname='account', label=_('Account'), fieldtype='Link', options='Account', hidden=1),
        dict(fieldname='currency', label=_('Currency'), fieldtype='Data', hidden=1),
    ]
