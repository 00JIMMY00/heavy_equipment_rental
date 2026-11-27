"""Posted grouped expenses and stock consumption for operating repairs."""
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
    for dt in ('Grouped Expense', 'Journal Entry'):
        frappe.has_permission(dt, 'read', throw=True)
    for field, dt in (('crane', 'Crane'), ('timesheet', 'Crane Timesheet'),
                      ('assignment', 'Rental Contract'), ('expense_type', 'Expense Entry Type'),
                      ('employee', 'Employee'), ('mode_of_payment', 'Mode of Payment'),
                      ('cost_center', 'Cost Center'), ('grouped_expense', 'Grouped Expense')):
        if f.get(field):
            frappe.get_doc(dt, f[field]).check_permission('read')
    currency = frappe.get_cached_value('Company', f.company, 'default_currency')
    rows = expense_rows(f, currency)
    rows.sort(key=lambda r: (r['posting_date'], r['source_type'], r['source'], r['row_number']))
    total = sum(r['amount'] for r in rows)
    grouping = f.get('group_by') or 'Crane'
    data = group_rows(rows, grouping, cint(f.get('show_details')), currency)
    total_label = _('Total Expenses')
    if data:
        data = [*data, dict(crane_name=total_label, amount=total, currency=currency, indent=0, is_total_row=1)]
    summary = [dict(label=total_label, value=total, datatype='Currency', currency=currency)]
    return columns(), data, None, expense_chart(rows, f.get('chart_by') or 'Crane', currency), summary, True


def expense_rows(f, currency):
    base = dict(company=f.company, docstatus=1)
    for field, target in (('crane', 'crane'), ('timesheet', 'crane_timesheet'),
                          ('assignment', 'crane_assignment'), ('employee', 'employee'),
                          ('cost_center', 'cost_center'), ('grouped_expense', 'name')):
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

    def append(source, row, journal_name, account=None):
        day = getdate(row.posting_date)
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
            expense_type=row.expense_entry_type,
            expense_type_title=title('Expense Entry Type', row.expense_entry_type, 'title'),
            mode_of_payment=row.mode_of_payment, cost_center=source.cost_center, description=row.description,
            amount=flt(row.amount), currency=currency, account=account,
            source_type=source.doctype, source=source.name, journal_entry=journal.name,
            row_number=row.idx, label=row.description,
            indent=0, is_group=0, line_count=1))

    # Each grouped row has either a direct journal or its original accounting voucher.
    for name in frappe.get_list('Grouped Expense', filters=base, pluck='name', limit_page_length=0):
        batch = frappe.get_doc('Grouped Expense', name)
        # Saved filters from before the merge can still isolate standalone originals.
        if f.source == 'Expense Entry' and not batch.legacy_expense:
            continue
        for row in batch.items:
            if not first <= getdate(row.posting_date) <= last:
                continue
            if f.expense_type and row.expense_entry_type != f.expense_type:
                continue
            if f.mode_of_payment and row.mode_of_payment != f.mode_of_payment:
                continue
            if row.journal_entry:
                append(batch, row, row.journal_entry)
            elif row.expense_entry:
                legacy = frappe.get_doc('Expense Entry', row.expense_entry)
                legacy.check_permission('read')
                if legacy.docstatus != 1:
                    frappe.throw(_('Expense {0} is not submitted.').format(legacy.name))
                line = legacy.expenses[row.idx - 1] if batch.legacy_expense else legacy.expenses[0]
                append(batch, row, legacy.journal_entry, line.expense_entry_account)
            else:
                frappe.throw(_("Expense {0} has no posted journal.").format(batch.name))
    result.extend(
        dict(row, currency=currency, crane_name=title('Crane', row['crane'], 'crane_name'))
        for row in maintenance_stock_rows(f)
    )
    return result


def maintenance_stock_rows(f):
    # These filters describe paid expense rows and do not apply to stock consumption.
    if f.source in ('Grouped Expense', 'Expense Entry') or any(
        f.get(field) for field in ('expense_type', 'grouped_expense', 'mode_of_payment', 'employee')
    ):
        return
    doctypes = ('Stock Entry', 'Crane Maintenance', 'GL Entry', 'Account')
    if not all(frappe.has_permission(doctype, 'read') for doctype in doctypes):
        return

    issue_filters = {
        'company': f.company, 'docstatus': 1, 'purpose': 'Material Issue',
        'posting_date': ['between', [f.from_date, f.to_date]], 'crane_maintenance': ['is', 'set'],
    }
    issues = {row.name: row for row in frappe.get_list('Stock Entry', filters=issue_filters,
        fields=['name', 'posting_date', 'crane_maintenance'], limit_page_length=0)}
    if not issues:
        return

    links = (('crane', 'crane', 'Crane'), ('timesheet', 'crane_timesheet', 'Crane Timesheet'),
        ('assignment', 'crane_assignment', 'Rental Contract'))
    job_filters = dict(company=f.company, cost_treatment='Operating Expense', docstatus=['!=', 2],
        name=['in', sorted({issue.crane_maintenance for issue in issues.values()})])
    job_filters.update({field: f[filter_name] for filter_name, field, _doctype in links if f.get(filter_name)})
    jobs = {
        job.name: job for job in frappe.get_list('Crane Maintenance', filters=job_filters,
            fields=['name', 'description', *(field for _filter_name, field, _doctype in links)], limit_page_length=0)
        if all(not job[field] or frappe.has_permission(doctype, 'read', doc=job[field])
            for _filter_name, field, doctype in links)
    }
    if not jobs:
        return

    accounts = frappe.get_list('Account', filters=dict(company=f.company, root_type='Expense', is_group=0),
        pluck='name', limit_page_length=0)
    if not accounts:
        return

    ledger_filters = dict(company=f.company, is_cancelled=0, voucher_type='Stock Entry', account=['in', accounts],
        voucher_no=['in', [name for name, issue in issues.items() if issue.crane_maintenance in jobs]])
    if f.cost_center:
        ledger_filters['cost_center'] = f.cost_center
    ledger = frappe.get_list('GL Entry', filters=ledger_filters,
        fields=['voucher_no', 'account', 'cost_center', 'sum(debit - credit) as amount'],
        group_by='voucher_no, account, cost_center', order_by='voucher_no, account, cost_center',
        limit_page_length=0)
    for number, line in enumerate(ledger, start=1):
        amount = flt(line.amount)
        if not amount:
            continue
        issue = issues[line.voucher_no]
        job = jobs[issue.crane_maintenance]
        day = str(issue.posting_date)
        yield dict(posting_date=day, month=day[:7], crane=job.crane, timesheet=job.crane_timesheet,
            assignment=job.crane_assignment, maintenance=job.name, expense_type_title=_('Maintenance Stock Issue'),
            description=job.description or _('Crane Maintenance'), cost_center=line.cost_center,
            amount=amount, account=line.account, source_type='Stock Entry', source=issue.name,
            row_number=number, indent=0, is_group=0, line_count=1)


def group_label(row, group):
    field = GROUPS[group]
    value = row.get(field)
    if group == 'Crane' and value:
        return row["crane_name"]
    if group == 'Expense Type':
        return f"{row['expense_type_title']} · {value}" if value else row['expense_type_title']
    return value or _('Unassigned')


def group_key(row, group):
    return row.get(GROUPS[group]) or '', group_label(row, group)


def group_rows(rows, group, details, currency):
    if group == 'None':
        return rows
    buckets = defaultdict(list)
    for row in rows:
        buckets[group_key(row, group)].append(row)
    totals = {key: sum(row['amount'] for row in members) for key, members in buckets.items()}
    keys = sorted(buckets) if group == 'Month' else sorted(buckets, key=lambda key: (-totals[key], key))
    result = []
    for key, label in keys:
        members = buckets[key, label]
        result.append(dict(crane=key if group == 'Crane' else None,
            crane_name=label if group == 'Crane' else '',
            description=label if group != 'Crane' else '', amount=totals[key, label],
            currency=currency, is_group=1, indent=0))
        if details:
            result.extend(dict(row, indent=1) for row in members)
    return result


def expense_chart(rows, group, currency):
    values = defaultdict(float)
    for row in rows:
        values[group_key(row, group)] += row['amount']
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
        col('mode_of_payment', 'Mode of Payment', 'Link', 150, 'Mode of Payment'),
        col('cost_center', 'Cost Center', 'Link', 170, 'Cost Center'),
        col('employee', 'Employee', 'Link', 145, 'Employee'),
    ]
