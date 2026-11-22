"""Post dated rows directly; preserve legacy Expense Entry sources."""
from math import isfinite

import erpnext
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class GroupedExpense(Document):
    def _validate_links(self):
        if self.is_new() and self.amended_from:
            original = frappe.get_doc(self.doctype, self.amended_from)
            if original.docstatus == 2:
                if self.profit_settlement == original.profit_settlement:
                    self.profit_settlement = None  # Derived again from the selected Timesheet.
                if self.legacy_expense == original.legacy_expense:
                    self.legacy_expense = None
                old_journals = {row.journal_entry for row in original.items}
                for row in self.items:
                    if row.journal_entry in old_journals:
                        row.journal_entry = None
                old_links = {row.expense_entry for row in original.items}
                for row in self.items:
                    if row.expense_entry in old_links:
                        row.expense_entry = None
        super()._validate_links()

    def validate(self):
        from heavy_equipment_rental.consolidated_expenses import get_defaults
        defaults = get_defaults(self.company)
        self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        self.mode_of_payment = self.mode_of_payment or defaults.get('mode_of_payment')
        from heavy_equipment_rental.rental_validation import lock_cranes
        sheet = None
        if self.timesheet_salary_payment:
            if not self.crane_timesheet:
                frappe.throw(_("Select a driver from a draft or submitted Timesheet."))
            sheet = frappe.get_doc("Crane Timesheet", self.crane_timesheet, for_update=True)
        if self.crane:
            lock_cranes([self.crane])
        previous = self.get_doc_before_save()
        if (self.legacy_expense or None) != (previous.legacy_expense if previous else None):
            frappe.throw(_('The original expense reference is managed by migration.'))
        if self.crane_maintenance and not self.flags.from_maintenance and not (
                previous and previous.crane_maintenance == self.crane_maintenance):
            frappe.throw(_('Submit Maintenance to create its expense.'))
        if self.crane_timesheet:
            sheet = sheet or frappe.get_doc('Crane Timesheet', self.crane_timesheet)
            sheet.check_permission('read')
            if sheet.docstatus == 2 or sheet.crane != self.crane:
                frappe.throw(_('Select a non-cancelled Timesheet for this Crane.'))
            self.crane_assignment = sheet.assignment
            self.profit_settlement = sheet.profit_settlement and frappe.db.get_value(
                "Crane Profit Settlement", {"name": sheet.profit_settlement, "docstatus": ["!=", 2]}, "name"
            )
        else:
            if previous and previous.crane_timesheet and self.crane_assignment == previous.crane_assignment:
                self.crane_assignment = None
            self.profit_settlement = None
        if self.crane_assignment:
            contract = frappe.get_doc('Rental Contract', self.crane_assignment)
            contract.check_permission('read')
            if contract.company != self.company or not any(r.crane == self.crane and not r.cancelled for r in contract.assigned_cranes):
                frappe.throw(_('Select a Crane from a Rental Contract in the same Company.'))
        self.cost_center = self.cost_center or erpnext.get_default_cost_center(self.company)
        if not frappe.db.exists('Cost Center', dict(name=self.cost_center, company=self.company, is_group=0, disabled=0)):
            frappe.throw(_('Select an enabled, non-group Cost Center for this Company.'))
        if self.employee and frappe.db.get_value('Employee', self.employee, 'company') != self.company:
            frappe.throw(_('The Driver must belong to the selected Company.'))
        if not self.items:
            frappe.throw(_('Add at least one expense row.'))
        self.total = 0
        self.flags.salary_payment_lines = []
        for row in self.items:
            if row.expense_entry or row.journal_entry:
                frappe.throw(_('Expense Entry links are managed automatically.'))
            row.expense_entry_type = row.expense_entry_type or defaults.get('expense_type')
            row.mode_of_payment = row.mode_of_payment or self.mode_of_payment
            if not row.posting_date or not (row.description or '').strip():
                frappe.throw(_('Row {0}: Date and Description are required.').format(row.idx))
            row.posting_date = getdate(row.posting_date)
            if not isfinite(flt(row.amount)) or flt(row.amount, row.precision('amount')) <= 0:
                frappe.throw(_('Row {0}: Total must be a finite positive amount.').format(row.idx))
            row.amount = flt(row.amount, row.precision('amount'))
            debit, _credit = self.row_accounts(row)
            self.flags.salary_payment_lines.append((row.posting_date, debit, row.amount))
            self.total += row.amount
        if self.timesheet_salary_payment:
            from heavy_equipment_rental.driver_payroll import validate_installment
            validate_installment(self, sheet)
        if not isfinite(self.total):
            frappe.throw(_("The batch total must be finite."))
        self.total = flt(self.total, self.precision('total'))

    def before_submit(self):
        from heavy_equipment_rental.employee_salary import validate_salary_payment

        validate_salary_payment(self.company, self.employee, self.flags.salary_payment_lines)

    def row_accounts(self, row):
        from heavy_equipment_rental.payment import payment_account
        account = frappe.db.get_value('Expense Entry Type', dict(name=row.expense_entry_type,
            company=self.company, enabled=1), 'account')
        common = dict(company=self.company, is_group=0, disabled=0, account_currency=self.currency)
        if not account or not frappe.db.exists('Account', dict(common, name=account, root_type='Expense')):
            frappe.throw(_('Row {0}: Select an enabled expense type with a company expense account.').format(row.idx))
        credit = payment_account(row.mode_of_payment, self.company)
        details = frappe.db.get_value('Account', dict(common, name=credit), ['root_type', 'account_type'], as_dict=True)
        if not details or details.root_type not in ('Asset', 'Liability') or details.account_type in ('Receivable', 'Payable'):
            frappe.throw(_('Select an enabled company payment account in the company currency.'))
        return account, credit

    def rental_source(self, row):
        return frappe._dict(doctype="Journal Entry" if row.journal_entry else self.doctype,
            name=row.journal_entry or self.name, company=self.company,
            crane=self.crane, crane_timesheet=self.crane_timesheet, crane_assignment=self.crane_assignment,
            posting_date=row.posting_date, service_from_date=row.posting_date, service_to_date=row.posting_date)

    def on_submit(self):
        from heavy_equipment_rental.rental_expenses import guard_expense
        for row in self.items:
            guard_expense(self.rental_source(row))
            account, payment = self.row_accounts(row)
            debit = dict(account=account, debit_in_account_currency=row.amount,
                cost_center=self.cost_center, crane=self.crane)
            if self.employee:
                debit.update(party_type='Employee', party=self.employee)
            journal = frappe.get_doc(dict(doctype='Journal Entry', company=self.company,
                posting_date=row.posting_date, mode_of_payment=row.mode_of_payment,
                user_remark=f'{self.name} / {row.idx}: {row.description}',
                accounts=[debit, dict(account=payment,
                    credit_in_account_currency=row.amount, crane=self.crane)]))
            journal.insert()
            row.db_set('journal_entry', journal.name, update_modified=False)
            journal.submit()

    def before_cancel(self):
        from heavy_equipment_rental.driver_payroll import guard_payroll_cancel
        guard_payroll_cancel(self)
        if self.crane_maintenance and frappe.db.get_value('Crane Maintenance', self.crane_maintenance, 'docstatus') == 1:
            frappe.throw(_('Cancel Crane Maintenance {0} to reverse its expense.').format(self.crane_maintenance))

    def on_cancel(self):
        from heavy_equipment_rental.rental_expenses import guard_expense
        cancelled = set()
        for row in self.items:
            guard_expense(self.rental_source(row))
            target = ('Journal Entry', row.journal_entry) if row.journal_entry else ('Expense Entry', row.expense_entry)
            if target not in cancelled:
                frappe.get_doc(*target, for_update=True).cancel()
                cancelled.add(target)


def guard_expense_cancel(expense):
    parent = frappe.db.get_value('Grouped Expense Item', {
        'expense_entry': expense.name, 'docstatus': 1,
        'parenttype': 'Grouped Expense',
    }, 'parent')
    if parent and frappe.db.get_value('Grouped Expense', parent, 'docstatus') == 1:
        frappe.throw(_('Cancel Grouped Expense {0} to reverse this expense.').format(parent))
