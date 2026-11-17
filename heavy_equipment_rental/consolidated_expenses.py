"""Company defaults and the fixed, validated Excel entry template."""
from datetime import date, datetime
from io import BytesIO
from math import isfinite
from zipfile import ZipFile, BadZipFile

import frappe
from frappe import _
from frappe.utils import flt, getdate

HEADERS = ('Date / التاريخ', 'Description / البيان', 'Total / الإجمالي',
           'Expense Entry Type / نوع المصروف', 'Mode of Payment / طريقة الدفع')


@frappe.whitelist()
def get_defaults(company):
    if not frappe.has_permission('Consolidated Expense', 'create'):
        frappe.throw(_('Not permitted'), frappe.PermissionError)
    frappe.get_doc('Company', company).check_permission('read')
    settings = frappe.get_cached_doc('Heavy Equipment Rental Settings')
    row = next((r for r in settings.expense_defaults if r.company == company), None)
    return dict(expense_type=row.expense_type, mode_of_payment=row.mode_of_payment) if row else {}


def validate_defaults(settings):
    seen = set()
    for row in settings.expense_defaults:
        if row.company in seen:
            frappe.throw(_('Set expense defaults only once per Company.'))
        seen.add(row.company)
        if row.expense_type:
            entry = frappe.get_doc('Expense Entry Type', row.expense_type)
            if entry.company != row.company or not entry.enabled:
                frappe.throw(_('Select an enabled Expense Entry Type for this Company.'))
        if row.mode_of_payment:
            from heavy_equipment_rental.driver_payroll import validate_payroll_mode
            validate_payroll_mode(row.mode_of_payment, row.company)


@frappe.whitelist()
def download_template():
    frappe.has_permission('Consolidated Expense', 'create', throw=True)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    book = Workbook()
    sheet = book.active
    sheet.title = 'Expenses'
    sheet.append(HEADERS)
    sheet.freeze_panes = 'A2'
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill('solid', fgColor='FFF0B3')
    for column, width in zip('ABCDE', (22, 55, 22, 40, 36)):
        sheet.column_dimensions[column].width = width
    instructions = book.create_sheet('Instructions')
    for line in (
        'Fill Expenses, keeping the header unchanged. Dates: YYYY-MM-DD or Excel dates. Maximum 1000 rows.',
        'Date, Description and Total are required. Total must be positive. No formulas.',
        'Type and payment mode may be blank to use the form defaults. Enter a type ID or its unique company title.',
        'Upload adds rows to the draft. Review them, Save, then Submit to post accounting.',
        'املأ التاريخ والبيان والإجمالي. اترك النوع وطريقة الدفع فارغين لاستخدام القيم الافتراضية.',
        'الرفع يضيف صفوفاً إلى المسودة. راجع البيانات ثم احفظ واعتمد لترحيل القيود.',
    ):
        instructions.append([line])
    instructions.column_dimensions['A'].width = 120
    output = BytesIO()
    book.save(output)
    frappe.response.update(type='binary', filename='consolidated-expenses.xlsx',
        filecontent=output.getvalue(), display_content_as='attachment')


def parse_template(content, company):
    from openpyxl import load_workbook
    if len(content) > 2 * 1024 * 1024:
        frappe.throw(_('The template must be smaller than 2 MB.'))
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 20 * 1024 * 1024:
                frappe.throw(_("The workbook is too large."))
    except BadZipFile:
        frappe.throw(_("Upload a valid .xlsx workbook."))
    book = load_workbook(BytesIO(content), read_only=True, data_only=False)
    try:
        if 'Expenses' not in book.sheetnames:
            frappe.throw(_('Use the downloaded expense template.'))
        sheet = book['Expenses']
        sheet.reset_dimensions()
        sheet.calculate_dimension(force=True)
        if sheet.max_row > 1001 or sheet.max_column != len(HEADERS):
            frappe.throw(_('Use the five-column template with at most 1000 rows.'))
        rows = sheet.iter_rows()
        if tuple(c.value for c in next(rows)) != HEADERS:
            frappe.throw(_('Use the downloaded expense template without changing its headers.'))
        result = []
        for index, cells in enumerate(rows, 2):
            values = [c.value for c in cells]
            if all(v is None for v in values):
                continue
            if any(c.data_type in ('f', 'e') for c in cells):
                frappe.throw(_('Excel row {0}: Formulas and errors are not allowed.').format(index))
            day, description, amount, expense_type, mode = values
            if not isinstance(day, (str, date, datetime)) or not str(description or '').strip():
                frappe.throw(_('Excel row {0}: Date and Description are required.').format(index))
            try:
                day = getdate(day)
                amount = float(amount)
                if not isfinite(amount) or amount <= 0:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                frappe.throw(_('Excel row {0}: Enter a valid date and positive total.').format(index))
            if expense_type:
                matches = frappe.get_list('Expense Entry Type', filters={
                    'company': company, 'enabled': 1},
                    or_filters={'name': str(expense_type), 'title': str(expense_type)}, pluck='name')
                if len(matches) != 1:
                    frappe.throw(_('Excel row {0}: Select a unique enabled expense type for this Company.').format(index))
                expense_type = matches[0]
            if mode:
                mode = str(mode)
                if not frappe.db.exists('Mode of Payment', {'name': mode, 'enabled': 1}):
                    frappe.throw(_('Excel row {0}: Invalid Mode of Payment.').format(index))
            result.append(dict(posting_date=str(day), description=str(description).strip(),
                amount=amount, expense_entry_type=expense_type, mode_of_payment=mode))
        if not result:
            frappe.throw(_('Add at least one expense row.'))
        return result
    finally:
        book.close()


@frappe.whitelist()
def upload_template(file_url, company):
    frappe.has_permission('Consolidated Expense', 'create', throw=True)
    frappe.get_doc('Company', company).check_permission('read')
    file = frappe.get_doc('File', {'file_url': file_url})
    file.check_permission('read')
    if not file.file_name.lower().endswith('.xlsx'):
        frappe.throw(_('Upload the .xlsx expense template.'))
    return parse_template(file.get_content(), company)
