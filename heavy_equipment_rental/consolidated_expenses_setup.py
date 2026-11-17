"""Portable fixtures: resolve each site's actual companies and chart of accounts."""
import frappe


def seed_defaults():
    settings = frappe.get_single('Heavy Equipment Rental Settings')
    changed = False
    for company in frappe.get_all('Company', fields=['name', 'default_expense_account', 'default_currency']):
        default = next((row for row in settings.expense_defaults if row.company == company.name), None)
        if default and default.expense_type:
            continue
        parent = frappe.db.get_value('Account', company.default_expense_account, 'parent_account') if company.default_expense_account else None
        parent = parent or frappe.db.get_value('Account', {
            'company': company.name, 'root_type': 'Expense', 'is_group': 1, 'disabled': 0,
        }, 'name', order_by='lft desc')
        if not parent:
            continue  # Setup wizard has not created this company's chart yet.
        account = frappe.db.get_value('Account', {
            'company': company.name, 'account_name': 'عام', 'root_type': 'Expense',
            'is_group': 0, 'disabled': 0, 'account_currency': company.default_currency,
        }, 'name')
        if not account:
            account = frappe.get_doc(dict(doctype='Account', account_name='عام',
                company=company.name, parent_account=parent, root_type='Expense',
                report_type='Profit and Loss', account_currency=company.default_currency,
                is_group=0)).insert(ignore_permissions=True).name
        expense_type = frappe.db.get_value('Expense Entry Type', {
            'company': company.name, 'title': 'عام', 'account': account, 'enabled': 1,
        }, 'name')
        if not expense_type:
            expense_type = frappe.get_doc(dict(doctype='Expense Entry Type', title='عام',
                company=company.name, account=account, enabled=1)).insert(ignore_permissions=True).name
        if not default:
            default = settings.append('expense_defaults', {'company': company.name})
        default.expense_type = expense_type
        changed = True
    if changed:
        # Only insert/update this new defaults table; don't validate unrelated settings.
        for row in settings.expense_defaults:
            if row.is_new():
                row.db_insert()
            else:
                row.db_update()
        frappe.clear_document_cache('Heavy Equipment Rental Settings', 'Heavy Equipment Rental Settings')


def update_workspace():
    key = 'her_grouped_expense_workspace_v3'
    if frappe.db.get_default(key) or not frappe.db.exists('Workspace', 'Crane Operations'):
        return
    workspace = frappe.get_doc('Workspace', 'Crane Operations')
    for table in ('links', 'shortcuts'):
        for row in workspace.get(table):
            if row.link_to in ('Consolidated Expense', 'Grouped Expense'):
                row.link_to = 'Grouped Expense'
                row.label = 'Grouped Expense'
    links = list(workspace.links)
    grouped = next((row for row in links if row.link_to == 'Grouped Expense'), None)
    if grouped:
        normal = next((row for row in links if row.link_to == 'Expense Entry'), None)
        if normal:
            links.remove(normal)
        else:
            normal = workspace.append('links', dict(type='Link', label='Expense Entry',
                link_type='DocType', link_to='Expense Entry'))
        links.insert(links.index(grouped) + 1, normal)
        workspace.set('links', links)
        for index, row in enumerate(workspace.links, 1):
            row.idx = index
        card = None
        for row in workspace.links:
            if row.type == 'Card Break':
                card = row
                card.link_count = 0
            elif card:
                card.link_count += 1
    was_in_patch = frappe.flags.in_patch
    frappe.flags.in_patch = True
    try:
        workspace.save(ignore_permissions=True)
        frappe.db.set_default(key, '1')
    finally:
        frappe.flags.in_patch = was_in_patch


def company_updated(doc, method=None):
    if frappe.db.exists("DocType", "HER Expense Defaults"):
        seed_defaults()
