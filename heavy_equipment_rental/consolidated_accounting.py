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
    guard_expense(batch.rental_source(row))
    return True


def sources(crane, company):
    for _, journal, source in fleet_sources([crane], company):
        yield journal, source


def fleet_sources(cranes, company, dates=None, assignment=None, *, include_legacy=False, unposted=None):
    if not cranes:
        return
    filters = [["Grouped Expense", "crane", "in", list(cranes)],
               ["Grouped Expense", "company", "=", company], ["Grouped Expense", "docstatus", "=", 1]]
    if assignment:
        filters.append(["Grouped Expense", "crane_assignment", "=", assignment])
    if dates:
        filters.append(["Grouped Expense Item", "posting_date", "between", dates])
    for name in frappe.get_all('Grouped Expense', filters=filters, distinct=True, pluck='name'):
        batch = frappe.get_doc('Grouped Expense', name)
        batch.check_permission('read')
        for row in batch.items:
            if dates and not dates[0] <= frappe.utils.getdate(row.posting_date) <= dates[1]:
                continue
            journal_name = row.journal_entry
            if row.expense_entry:
                if not include_legacy:
                    # Settlements retain the identity used in their posted snapshots.
                    continue
                original = frappe.get_doc('Expense Entry', row.expense_entry)
                original.check_permission('read')
                journal_name = original.journal_entry if original.docstatus == 1 else None
            journal = None
            if journal_name:
                try:
                    journal = frappe.get_doc('Journal Entry', journal_name)
                except frappe.DoesNotExistError:
                    pass
            if journal:
                journal.check_permission('read')
            if not journal or journal.docstatus != 1 or journal.company != company:
                if unposted is not None:
                    unposted.append(batch.name)
                    continue
                frappe.throw(_('Grouped Expense {0} has an invalid Journal Entry.').format(batch.name))
            yield batch.crane, journal, dict(doctype='Journal Entry', name=journal.name,
                journal=journal.name, posting_date=str(row.posting_date),
                rental_assignment=batch.crane_assignment, rental_timesheet=batch.crane_timesheet,
                service_from_date=str(row.posting_date), service_to_date=str(row.posting_date),
                basis='Selected Timesheet' if batch.crane_timesheet else 'Selected Rental Contract / worked hours', expenses=row.amount,
                consolidated_expense=batch.name, employee=batch.employee,
                description=row.description, mode_of_payment=row.mode_of_payment)
