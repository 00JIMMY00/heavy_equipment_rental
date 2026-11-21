"""Post repair purchases and consumption atomically from the maintenance form."""
import frappe
from frappe import _
from frappe.utils import flt, today

FINANCIAL_FIELDS = ('repair_method', 'use_existing_documents', 'repair_source', 'repair_supplier', 'supplier_invoice_no',
    'supplier_invoice_date', 'repair_expense_account', 'repair_cost_center', 'supplier_paid_amount', 'pay_full_amount', 'mode_of_payment')
LINK_FIELDS = ('repair_purchase_invoice', 'repair_material_issue', 'repair_payment_entry')


def financial_value(doc, field):
    if field in ('supplier_paid_amount', 'pay_full_amount'):
        return flt(doc.get(field))
    return doc.get(field) or ''


def validate_inputs(doc):
    before = doc.get_doc_before_save()
    if doc.is_new() and any(doc.get(field) for field in LINK_FIELDS + ('expense_entry', 'grouped_expense')):
        frappe.throw(_('Generated repair links cannot be supplied on a new Maintenance.'))
    normalize_method(doc)
    doc.repair_source = doc.repair_source or 'Manual Documents'
    if doc.repair_source != 'Manual Documents' and not doc.flags.posting_repair and not (before and before.status in ('Completed', 'Cancelled')):
        apply_defaults(doc)
    if before:
        if any(doc.get(f) != before.get(f) for f in LINK_FIELDS) and not doc.flags.posting_repair:
            frappe.throw(_('Generated repair links cannot be edited.'))
        from heavy_equipment_rental.crane_repairs import documents
        if documents(doc.name, check_permissions=False) and not doc.flags.posting_repair:
            old_items = [(r.item_code, r.qty, r.warehouse, r.rate) for r in before.get('repair_items', [])]
            new_items = [(r.item_code, r.qty, r.warehouse, r.rate) for r in doc.get('repair_items', [])]
            if old_items != new_items or any(financial_value(doc, f) != financial_value(before, f) for f in FINANCIAL_FIELDS):
                frappe.throw(_('Repair inputs cannot change after accounting documents exist. Create a separate repair for corrections.'))
    if doc.repair_source == 'Manual Documents':
        return
    if doc.cost_treatment not in ('Operating Expense', 'Capitalize Improvement'):
        frappe.throw(_('Automatic completion supports routine repairs and asset improvements.'))
    if doc.repair_source not in ('My Stock', 'External Parts', 'External Service', 'Supplier Bill'):
        frappe.throw(_('Select a valid Repair Source.'))


def validate_posting(job):
    if job.repair_source not in ('My Stock', 'External Parts', 'External Service', 'Supplier Bill') or job.cost_treatment not in ('Operating Expense', 'Capitalize Improvement'):
        frappe.throw(_('Select parts from stock, purchased parts or an external service.'))
    if not job.repair_items:
        frappe.throw(_('Add the repair items or services.'))
    if job.repair_source != 'My Stock' and not job.repair_supplier:
        frappe.throw(_('Select the repair Supplier.'))
    company = frappe.get_cached_doc('Company', job.company)
    job.repair_expense_account = job.repair_expense_account or repair_defaults(job.company).get('expense_account')
    job.repair_cost_center = job.repair_cost_center or company.cost_center
    if not job.repair_expense_account or not job.repair_cost_center:
        frappe.throw(_('Set the Repair Expense Account in HER Settings → Maintenance Defaults and select a Cost Center.'))
    account = frappe.get_doc('Account', job.repair_expense_account)
    account.check_permission('read')
    if account.company != job.company or account.root_type != 'Expense' or account.is_group or account.disabled:
        frappe.throw(_('Select an enabled company Expense account.'))
    center = frappe.get_doc('Cost Center', job.repair_cost_center)
    center.check_permission('read')
    if center.company != job.company or center.is_group or center.disabled:
        frappe.throw(_('Select an enabled company Cost Center.'))
    if job.repair_source in ('External Parts', 'Supplier Bill') and any(frappe.get_cached_value('Item', r.item_code, 'is_stock_item') for r in job.repair_items):
        warehouse = maintenance_warehouse(job.company)
        for row in job.repair_items:
            row.warehouse = warehouse if frappe.get_cached_value('Item', row.item_code, 'is_stock_item') else None
    for row in job.repair_items:
        item = frappe.get_doc('Item', row.item_code)
        item.check_permission('read')
        if item.disabled or item.is_fixed_asset or (job.repair_source != 'Supplier Bill' and bool(item.is_stock_item) != (job.repair_source != 'External Service')):
            frappe.throw(_('Use stock Items for parts and non-stock Items for external services.'))
        if item.has_serial_no or item.has_batch_no:
            frappe.throw(_('Serial/batch Items require the manual native document workflow; select Manual Documents.'))
        if flt(row.qty) <= 0 or (job.repair_source != 'My Stock' and flt(row.rate) <= 0):
            frappe.throw(_('Enter positive quantities and positive purchase rates for external purchases.'))
        if item.is_stock_item:
            warehouse = frappe.get_doc('Warehouse', row.warehouse)
            warehouse.check_permission('read')
            if warehouse.company != job.company or warehouse.is_group or warehouse.disabled:
                frappe.throw(_('Select an enabled company Warehouse for every part.'))


@frappe.whitelist(methods=['POST'])
def post_and_complete(maintenance):
    """Compatibility endpoint for old open forms: always use native submission."""
    job = frappe.get_doc('Crane Maintenance', maintenance, for_update=True)
    job.check_permission('read')
    if job.docstatus == 1:
        return job.name
    job.submit()
    return job.name


def post_documents(job):
    """Called only from Maintenance on_submit, in its native transaction."""
    from heavy_equipment_rental.crane_repairs import documents
    if documents(job.name, check_permissions=False):
        frappe.throw(_('Accounting documents already exist. Use their existing manual workflow or cancel and amend Maintenance.'))
    common = dict(company=job.company, crane=job.crane, crane_maintenance=job.name,
        posting_date=job.actual_end_date, set_posting_time=1)
    stock_rows = [r for r in job.repair_items if frappe.get_cached_value('Item', r.item_code, 'is_stock_item')]
    if job.repair_source != 'My Stock':
        invoice = frappe.get_doc(dict(doctype='Purchase Invoice', **common,
            supplier=job.repair_supplier, update_stock=int(bool(stock_rows)),
            bill_no=job.supplier_invoice_no, bill_date=job.supplier_invoice_date))
        for row in job.repair_items:
            invoice.append('items', dict(item_code=row.item_code, qty=row.qty, rate=row.rate,
                warehouse=row.warehouse if row in stock_rows else None,
                expense_account=job.repair_expense_account, cost_center=job.repair_cost_center))
        invoice.insert()
        invoice.submit()
        job.repair_purchase_invoice = invoice.name
    if job.cost_treatment == 'Capitalize Improvement':
        from heavy_equipment_rental.crane_repairs import make_repair_document
        repair = frappe.get_doc(make_repair_document(job.name, 'Asset Repair'))
        if job.repair_source != 'My Stock' and len(stock_rows) < len(job.repair_items):
            repair.purchase_invoice = invoice.name
        if stock_rows:
            repair.stock_consumption = 1
            for row in stock_rows:
                repair.append('stock_items', dict(item_code=row.item_code, warehouse=row.warehouse,
                    consumed_quantity=row.qty, valuation_rate=0))
        repair.insert().submit()
        job.repair_material_issue = frappe.db.get_value('Stock Entry',
            {'asset_repair': repair.name, 'docstatus': 1}, 'name')
    elif stock_rows:
        issue = frappe.get_doc(dict(doctype='Stock Entry', **common,
            stock_entry_type='Material Issue', purpose='Material Issue'))
        for row in stock_rows:
            issue.append('items', dict(item_code=row.item_code, qty=row.qty, s_warehouse=row.warehouse,
                expense_account=job.repair_expense_account, cost_center=job.repair_cost_center))
        issue.insert()
        issue.submit()
        job.repair_material_issue = issue.name
    if job.repair_source != 'My Stock':
        pay_supplier(job, invoice)
    for field in LINK_FIELDS + ('supplier_paid_amount',):
        job.db_set(field, flt(job.get(field)) if field == 'supplier_paid_amount' else job.get(field), update_modified=False)
    return job.name


def repair_defaults(company):
    row = frappe.db.get_value('HER Repair Defaults',
        {'parent': 'Heavy Equipment Rental Settings', 'parenttype': 'Heavy Equipment Rental Settings', 'company': company},
        ['expense_account', 'warehouse', 'mode_of_payment'], as_dict=True)
    return row or frappe._dict()


@frappe.whitelist()
def get_repair_defaults(company):
    frappe.has_permission('Crane Maintenance', 'read', throw=True)
    frappe.get_doc('Company', company).check_permission('read')
    defaults = repair_defaults(company)
    defaults.cost_center = frappe.get_cached_value('Company', company, 'cost_center')
    return defaults


def apply_defaults(job):
    if not job.company:
        return
    defaults = repair_defaults(job.company)
    job.repair_expense_account = job.repair_expense_account or defaults.get('expense_account')
    job.repair_cost_center = job.repair_cost_center or frappe.get_cached_value('Company', job.company, 'cost_center')
    job.mode_of_payment = job.mode_of_payment or defaults.get('mode_of_payment')
    if job.pay_full_amount and job.repair_source in ('External Parts', 'External Service', 'Supplier Bill'):
        job.supplier_paid_amount = sum(flt(r.qty) * flt(r.rate) for r in job.repair_items)


def maintenance_warehouse(company):
    configured = repair_defaults(company).get('warehouse')
    if configured:
        return configured
    # Serialize creation across different repairs in the same company.
    frappe.db.sql('SELECT name FROM tabCompany WHERE name=%s FOR UPDATE', company)
    name = frappe.db.get_value('Warehouse', {'company': company, 'warehouse_name': 'Maintenance', 'is_group': 0})
    if not name:
        parent = frappe.db.get_value('Warehouse', {'company': company, 'is_group': 1, 'parent_warehouse': ['is', 'not set']})
        name = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='Maintenance', company=company,
            parent_warehouse=parent)).insert().name
    return name


def pay_supplier(job, invoice):
    amount = flt(invoice.outstanding_amount if job.pay_full_amount else job.supplier_paid_amount,
        invoice.precision('outstanding_amount'))
    if amount < 0 or amount > flt(invoice.outstanding_amount):
        frappe.throw(_('Paid Amount must be between zero and the invoice outstanding amount.'))
    job.supplier_paid_amount = amount
    if not amount:
        return
    from heavy_equipment_rental.payment import payment_account
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    account = payment_account(job.mode_of_payment, job.company)
    if frappe.get_cached_value('Account', account, 'account_currency') != invoice.currency:
        frappe.throw(_('Use a supplier payment account in the invoice currency.'))
    payment = get_payment_entry('Purchase Invoice', invoice.name, party_amount=amount,
        bank_account=account, bank_amount=amount)
    payment.mode_of_payment = job.mode_of_payment
    payment.posting_date = job.actual_end_date
    payment.reference_no = job.supplier_invoice_no or job.name
    payment.reference_date = job.supplier_invoice_date or job.actual_end_date
    payment.insert()
    payment.submit()
    job.repair_payment_entry = payment.name


def validate_repair_defaults(settings):
    companies = set()
    for row in settings.get('repair_defaults', []):
        if row.company in companies:
            frappe.throw(_('Set only one Maintenance Defaults row per Company.'))
        companies.add(row.company)
        account = frappe.get_doc('Account', row.expense_account)
        if account.company != row.company or account.root_type != 'Expense' or account.is_group or account.disabled:
            frappe.throw(_('Maintenance Defaults requires an enabled Expense account in the selected Company.'))
        if row.warehouse:
            warehouse = frappe.get_doc('Warehouse', row.warehouse)
            if warehouse.company != row.company or warehouse.is_group or warehouse.disabled:
                frappe.throw(_('Maintenance Warehouse must be an enabled company warehouse.'))
        if row.mode_of_payment:
            from heavy_equipment_rental.payment import payment_account
            payment_account(row.mode_of_payment, row.company)


def normalize_method(doc):
    # Blank method preserves older API/manual workflows and their historical data.
    if doc.get_doc_before_save() and doc.get_doc_before_save().docstatus != 0:
        return
    if not doc.get('repair_method'):
        return
    if doc.get('use_existing_documents') or doc.cost_treatment in ('No Cost', 'Recover from Owner'):
        doc.repair_source = 'Manual Documents'
        return
    if doc.repair_method == 'Quick Repair':
        doc.repair_source = 'Manual Documents'
        doc.cost_treatment = 'Cash Expense'
        apply_defaults(doc)
        configured_account = repair_defaults(doc.company).get('expense_account') if doc.company else None
        if configured_account:
            doc.repair_expense_account = configured_account
        if doc.company and configured_account:
            doc.expense_type = frappe.db.get_value('Expense Entry Type', {
                'company': doc.company, 'account': doc.repair_expense_account, 'enabled': 1}, 'name')
            if not doc.expense_type:
                doc.expense_type = frappe.get_doc(dict(doctype='Expense Entry Type',
                    title='Crane Maintenance', company=doc.company,
                    account=doc.repair_expense_account, enabled=1)).insert(ignore_permissions=True).name
        elif doc._action == 'submit':
            frappe.throw(_('Set the Repair Expense Account in HER Settings → Maintenance Defaults.'))
    elif doc.repair_method in ('Use Stock Parts', 'Supplier Bill'):
        doc.repair_source = 'My Stock' if doc.repair_method == 'Use Stock Parts' else 'Supplier Bill'
        if doc.cost_treatment in (None, '', 'Cash Expense'):
            doc.cost_treatment = 'Operating Expense'
    else:
        frappe.throw(_('Select a valid repair method.'))
