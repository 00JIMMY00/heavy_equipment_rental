"""A dated expense batch; existing Expense Entries remain the accounting sources."""
from math import isfinite

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class ConsolidatedExpense(Document):
    def _validate_links(self):
        if self.is_new() and self.amended_from:
            original = frappe.get_doc(self.doctype, self.amended_from)
            if original.docstatus == 2:
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
            if row.expense_entry:
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
            expense.insert()
            expense.submit()
            row.db_set('expense_entry', expense.name, update_modified=False)

    def on_cancel(self):
        for row in self.items:
            expense = frappe.get_doc('Expense Entry', row.expense_entry, for_update=True)
            if expense.docstatus != 1:
                frappe.throw(_('The linked Expense Entry must be submitted.'))
            expense.cancel()


def guard_expense_cancel(expense):
    parent = frappe.db.get_value('Consolidated Expense Item', {
        'expense_entry': expense.name, 'docstatus': 1,
        'parenttype': 'Consolidated Expense',
    }, 'parent')
    if parent and frappe.db.get_value('Consolidated Expense', parent, 'docstatus') == 1:
        frappe.throw(_('Cancel Consolidated Expense {0} to reverse this expense.').format(parent))
