"""Post dated rows directly; preserve legacy Expense Entry sources."""
from math import isfinite

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class GroupedExpense(Document):
    def _validate_links(self):
        if self.is_new() and self.amended_from:
            original = frappe.get_doc(self.doctype, self.amended_from)
            if original.docstatus == 2:
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
        sheet = frappe.get_doc('Crane Timesheet', self.crane_timesheet)
        sheet.check_permission('read')
        if sheet.docstatus == 2 or sheet.crane != self.crane:
            frappe.throw(_('Select a non-cancelled Timesheet for this Crane.'))
        self.crane_assignment = sheet.assignment
        self.profit_settlement = sheet.profit_settlement
        if self.employee and frappe.db.get_value('Employee', self.employee, 'company') != self.company:
            frappe.throw(_('The Driver must belong to the selected Company.'))
        if not self.items:
            frappe.throw(_('Add at least one expense row.'))
        self.total = 0
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
            expense = self.make_expense(row)
            expense.validate()
            self.cost_center = expense.cost_center
            # The shared controller validates currency, company and account class.
            account = expense.expenses[0].expense_entry_account
            if frappe.db.get_value('Account', account, 'disabled'):
                frappe.throw(_('The Expense Account is disabled.'))
            payment = expense.get_accounting_details()
            if frappe.db.get_value('Account', payment, 'disabled'):
                frappe.throw(_('The payment account is disabled.'))
            self.total += row.amount
        if not isfinite(self.total):
            frappe.throw(_("The batch total must be finite."))
        self.total = flt(self.total, self.precision('total'))

    def make_expense(self, row):
        return frappe.get_doc(dict(
            doctype='Expense Entry', company=self.company,
            posting_date=row.posting_date, description=row.description,
            crane=self.crane, crane_timesheet=self.crane_timesheet,
            crane_assignment=self.crane_assignment, employee=self.employee,
            mode_of_payment=row.mode_of_payment, cost_center=self.cost_center,
            expenses=[dict(expense_entry_type=row.expense_entry_type, amount=row.amount)],
        ))

    def on_submit(self):
        # Native request transaction rolls back the whole batch on any failure.
        for row in self.items:
            expense = self.make_expense(row)
            expense.validate()
            from heavy_equipment_rental.rental_expenses import guard_expense
            guard_expense(expense)
            debit = dict(account=expense.expenses[0].expense_entry_account,
                debit_in_account_currency=row.amount, cost_center=self.cost_center, crane=self.crane)
            if self.employee:
                debit.update(party_type='Employee', party=self.employee)
            journal = frappe.get_doc(dict(doctype='Journal Entry', company=self.company,
                posting_date=row.posting_date, mode_of_payment=row.mode_of_payment,
                user_remark=f'{self.name} / {row.idx}: {row.description}',
                accounts=[debit, dict(account=expense.get_accounting_details(),
                    credit_in_account_currency=row.amount, crane=self.crane)]))
            journal.insert()
            row.db_set('journal_entry', journal.name, update_modified=False)
            journal.submit()

    def on_cancel(self):
        from heavy_equipment_rental.rental_expenses import guard_expense
        for row in self.items:
            guard_expense(self.make_expense(row))
            target = ('Journal Entry', row.journal_entry) if row.journal_entry else ('Expense Entry', row.expense_entry)
            document = frappe.get_doc(*target, for_update=True)
            document.cancel()


def guard_expense_cancel(expense):
    parent = frappe.db.get_value('Grouped Expense Item', {
        'expense_entry': expense.name, 'docstatus': 1,
        'parenttype': 'Grouped Expense',
    }, 'parent')
    if parent and frappe.db.get_value('Grouped Expense', parent, 'docstatus') == 1:
        frappe.throw(_('Cancel Grouped Expense {0} to reverse this expense.').format(parent))
