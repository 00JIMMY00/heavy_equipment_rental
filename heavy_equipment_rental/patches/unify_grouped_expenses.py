"""Expose historical vouchers as grouped documents without generating accounting entries."""
import frappe


def execute():
    for name in frappe.get_all("Expense Entry", pluck="name", order_by="creation"):
        batch = frappe.db.get_value("Grouped Expense Item", {"expense_entry": name}, "parent")
        batch = batch or frappe.db.get_value("Grouped Expense", {"legacy_expense": name}, "name")
        if not batch:
            batch = copy_history(frappe.get_doc("Expense Entry", name))
        elif frappe.db.get_value("Grouped Expense", batch, "legacy_expense") == name:
            receipt = frappe.db.get_value("Expense Entry", name, "receipt")
            if receipt and not frappe.db.get_value("Grouped Expense", batch, "receipt"):
                frappe.db.set_value("Grouped Expense", batch, "receipt", receipt, update_modified=False)
        for dt in ("Crane Driver Payroll", "Crane Maintenance"):
            frappe.db.set_value(dt, {"expense_entry": name}, "grouped_expense", batch, update_modified=False)


def copy_history(original):
    batch = frappe.new_doc("Grouped Expense")
    batch.update({key: original.get(key) for key in (
        "receipt", "company", "cost_center", "mode_of_payment", "employee", "crane", "crane_timesheet",
        "crane_assignment", "crane_maintenance", "docstatus", "creation", "owner", "modified", "modified_by")})
    batch.legacy_expense = original.name
    batch.currency = frappe.get_cached_value("Company", original.company, "default_currency")
    batch.total = sum(row.amount for row in original.expenses)
    if original.amended_from:
        batch.amended_from = frappe.db.get_value("Grouped Expense", {"legacy_expense": original.amended_from}, "name")
    for line in original.expenses:
        batch.append("items", dict(posting_date=original.posting_date, description=original.description,
            expense_entry_type=line.expense_entry_type, amount=line.amount, mode_of_payment=original.mode_of_payment,
            expense_entry=original.name if original.docstatus else None, docstatus=original.docstatus))
    batch.set_new_name()
    batch.db_insert()
    for row in batch.items:
        row.parent = batch.name
        row.db_insert()
    return batch.name
