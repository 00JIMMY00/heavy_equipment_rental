"""Direct batch journals retain explicit rental attribution through their source row."""
import frappe
from frappe import _


def source_for_journal(name):
    parent = frappe.db.get_value('Grouped Expense Item', {'journal_entry': name}, 'parent')
    if not parent:
        return None, None
    batch = frappe.get_doc('Grouped Expense', parent)
    return batch, next(row for row in batch.items if row.journal_entry == name)


def guard_journal(doc, method=None):
    batch, row = source_for_journal(doc.name)
    if not batch:
        return False
    if doc._action == 'cancel' and batch.docstatus == 1:
        frappe.throw(_('Cancel Grouped Expense {0} to reverse this journal.').format(batch.name))
    from heavy_equipment_rental.rental_expenses import guard_expense
    guard_expense(batch.make_expense(row))
    return True


def sources(crane, company):
    for name in frappe.get_all('Grouped Expense', filters={'crane': crane, 'company': company, 'docstatus': 1}, pluck='name'):
        batch = frappe.get_doc('Grouped Expense', name)
        batch.check_permission('read')
        for row in batch.items:
            if not row.journal_entry:
                continue
            journal = frappe.get_doc('Journal Entry', row.journal_entry)
            journal.check_permission('read')
            if journal.docstatus != 1 or journal.company != company:
                frappe.throw(_('The batch has an invalid Journal Entry.'))
            yield journal, dict(doctype='Journal Entry', name=journal.name,
                journal=journal.name, posting_date=str(row.posting_date),
                rental_assignment=batch.crane_assignment, rental_timesheet=batch.crane_timesheet,
                service_from_date=str(row.posting_date), service_to_date=str(row.posting_date),
                basis='Selected Timesheet', expenses=row.amount,
                consolidated_expense=batch.name, employee=batch.employee,
                description=row.description, mode_of_payment=row.mode_of_payment)
