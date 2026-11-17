"""Paid expense sources, with single-count legacy batches and rental drill-down."""
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

GROUPS = {'Crane': 'crane', 'Timesheet': 'timesheet', 'Expense Type': 'expense_type',
          'Mode of Payment': 'mode_of_payment', 'Month': 'month'}


def execute(filters=None):
    f = frappe._dict(filters or {})
    if not all(f.get(k) for k in ('company', 'from_date', 'to_date')):
        frappe.throw(_('Company, From Date and To Date are required.'))
    if getdate(f.from_date) > getdate(f.to_date):
        frappe.throw(_('From Date must be before To Date.'))
    if f.get('group_by', 'Crane') not in ('None', *GROUPS):
        frappe.throw(_('Invalid grouping.'))
    if f.get('source', 'All') not in ('All', 'Grouped Expense', 'Expense Entry'):
        frappe.throw(_('Invalid expense source.'))
    if f.get('chart_by', 'Crane') not in ('Crane', 'Expense Type', 'Month'):
        frappe.throw(_('Invalid chart grouping.'))
    frappe.get_doc('Company', f.company).check_permission('read')
    for dt in ('Expense Entry', 'Grouped Expense', 'Journal Entry'):
        frappe.has_permission(dt, 'read', throw=True)
    for field, dt in (('crane', 'Crane'), ('timesheet', 'Crane Timesheet'),
                      ('assignment', 'Rental Contract'), ('expense_type', 'Expense Entry Type'),
                      ('employee', 'Employee'), ('mode_of_payment', 'Mode of Payment')):
        if f.get(field):
            frappe.get_doc(dt, f[field]).check_permission('read')
    currency = frappe.get_cached_value('Company', f.company, 'default_currency')
    rows = expense_rows(f, currency)
    rows.sort(key=lambda r: (r['posting_date'], r['source_type'], r['source'], r['row_number']))
    total = sum(r['amount'] for r in rows)
    grouping = f.get('group_by') or 'Crane'
    data = group_rows(rows, grouping, cint(f.get('show_details')), currency)
    summary = [dict(label=_('Total Expenses'), value=total, datatype='Currency', currency=currency)]
    return columns(), data, None, expense_chart(rows, f.get('chart_by') or 'Crane', currency), summary, True


def expense_rows(f, currency):
    base = dict(company=f.company, docstatus=1)
    for field, target in (('crane', 'crane'), ('timesheet', 'crane_timesheet'),
                          ('assignment', 'crane_assignment'), ('employee', 'employee')):
        if f.get(field):
            base[target] = f[field]
    first, last = getdate(f.from_date), getdate(f.to_date)
    result = []
    journals = {}
    titles = {}

    def title(dt, name, field):
        if not name:
            return _('Unassigned')
        key = (dt, name)
        if key not in titles:
            doc = frappe.get_doc(dt, name)
            doc.check_permission('read')
            titles[key] = doc.get(field) or name
        return titles[key]

    def append(source, row, journal_name):
        day = getdate(row.posting_date if source.doctype == 'Grouped Expense' else source.posting_date)
        if not first <= day <= last:
            return
        kind = row.expense_entry_type
        mode = row.mode_of_payment if source.doctype == 'Grouped Expense' else source.mode_of_payment
        if (f.expense_type and kind != f.expense_type) or (f.mode_of_payment and mode != f.mode_of_payment):
            return
        if f.source and f.source != 'All' and source.doctype != f.source:
            return
        if journal_name not in journals:
            if not journal_name:
                frappe.throw(_('Expense {0} has no posted journal.').format(source.name))
            journal = frappe.get_doc('Journal Entry', journal_name)
            journal.check_permission('read')
            if journal.docstatus != 1 or journal.company != f.company:
                frappe.throw(_('Expense {0} has no valid posted journal.').format(source.name))
            journals[journal_name] = journal
        journal = journals[journal_name]
        # Account comes from posted evidence, not the expense type's current default.
        account = row.get('expense_entry_account')
        if not account:
            account = next((r.account for r in journal.accounts if r.debit > 0), None)
        if source.crane_timesheet:
            frappe.get_doc('Crane Timesheet', source.crane_timesheet).check_permission('read')
        if source.crane_assignment:
            frappe.get_doc('Rental Contract', source.crane_assignment).check_permission('read')
        result.append(dict(posting_date=str(day), month=str(day)[:7],
            crane=source.crane, crane_name=title('Crane', source.crane, 'crane_name'),
            timesheet=source.crane_timesheet, assignment=source.crane_assignment,
            employee=source.employee, employee_name=title('Employee', source.employee, 'employee_name') if source.employee else '',
            expense_type=kind, expense_type_title=title('Expense Entry Type', kind, 'title'),
            mode_of_payment=mode, description=row.description if source.doctype == 'Grouped Expense' else source.description,
            amount=flt(row.amount), currency=currency, account=account,
            source_type=source.doctype, source=source.name, journal_entry=journal.name,
            row_number=row.idx, label=row.description if source.doctype == 'Grouped Expense' else source.description,
            indent=0, is_group=0, line_count=1))

    # Grouped documents own legacy Expense Entries too. Direct journals and legacy
    # sources are separate rows here; the latter are excluded from the normal pass.
    for name in frappe.get_list('Grouped Expense', filters=base, pluck='name', limit_page_length=0):
        batch = frappe.get_doc('Grouped Expense', name)
        for row in batch.items:
            if not first <= getdate(row.posting_date) <= last:
                continue
            if row.journal_entry:
                append(batch, row, row.journal_entry)
            elif row.expense_entry:
                legacy = frappe.get_doc('Expense Entry', row.expense_entry)
                legacy.check_permission('read')
                if legacy.docstatus != 1:
                    frappe.throw(_('Expense {0} is not submitted.').format(legacy.name))
                append(batch, row, legacy.journal_entry)
            else:
                frappe.throw(_("Expense {0} has no posted journal.").format(batch.name))
    normal_filters = dict(base, posting_date=['between', [f.from_date, f.to_date]])
    for name in frappe.get_list('Expense Entry', filters=normal_filters, pluck='name', limit_page_length=0):
        parent = frappe.db.get_value('Grouped Expense Item',
            {'expense_entry': name, 'parenttype': 'Grouped Expense', 'docstatus': 1}, 'parent')
        if parent:
            # Never expose an inaccessible batch through its legacy source.
            frappe.get_doc('Grouped Expense', parent).check_permission('read')
            continue
        expense = frappe.get_doc('Expense Entry', name)
        for row in expense.expenses:
            append(expense, row, expense.journal_entry)
    return result


def group_label(row, group):
    field = GROUPS[group]
    value = row.get(field)
    if group == 'Crane' and value:
        return row["crane_name"]
    if group == 'Expense Type' and value:
        return f"{row['expense_type_title']} · {value}"
    return value or _('Unassigned')


def group_rows(rows, group, details, currency):
    if group == 'None':
        return rows
    buckets = defaultdict(list)
    for row in rows:
        buckets[row.get(GROUPS[group]) or ''].append(row)
    totals = {key: sum(row['amount'] for row in members) for key, members in buckets.items()}
    keys = sorted(buckets) if group == 'Month' else sorted(buckets, key=lambda key: (-totals[key], key))
    result = []
    for key in keys:
        members = buckets[key]
        label = group_label(members[0], group)
        result.append(dict(crane=key if group == 'Crane' else None,
            crane_name=label if group == 'Crane' else '',
            description=label if group != 'Crane' else '', amount=totals[key],
            currency=currency, is_group=1, indent=0))
        if details:
            result.extend(dict(row, indent=1) for row in members)
    return result


def expense_chart(rows, group, currency):
    values = defaultdict(float)
    for row in rows:
        key = (row.get(GROUPS[group]) or '', group_label(row, group))
        values[key] += row['amount']
    order = sorted(values) if group == 'Month' else sorted(values, key=lambda key: (-values[key], key))
    items = [(key[1], values[key]) for key in order]
    if group != 'Month' and len(items) > 12:
        items = items[:11] + [(_('Other'), sum(v for _, v in items[11:]))]
    return dict(data=dict(labels=[k for k, _ in items], datasets=[dict(name=f"{_('Expenses')} ({currency})", values=[v for _, v in items])]),
        type='bar', height=280, colors=['#d00000'], barOptions=dict(spaceRatio=0.35),
        axisOptions=dict(xAxisMode='tick', yAxisMode='span', shortenYAxisNumbers=1))


def columns():
    def col(field, label, typ='Data', width=125, options=None):
        return dict(fieldname=field, label=_(label), fieldtype=typ, width=width, **({'options': options} if options else {}))
    return [
        col('posting_date', 'Posting Date', 'Date', 125),
        col('crane_name', 'Crane', width=190),
        col('amount', 'Amount', 'Currency', 150, 'currency'),
        col('description', 'Description', width=300),
        col('timesheet', 'Crane Timesheet', 'Link', 145, 'Crane Timesheet'),
        col('expense_type_title', 'Expense Type', width=150),
        col('source', 'Expense Document', 'Dynamic Link', 150, 'source_type'),
    ]
