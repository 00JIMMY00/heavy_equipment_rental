"""Explicit development-company reset with backup and an immutable deletion plan.

Never run by install/migration. Uses ERPNext's transaction-deletion cleanup helpers;
submitted sources and ledger are removed together, rather than faking cancellations.
"""

import gzip
import hashlib
import json
from pathlib import Path

import frappe


SITE = "cranes-dev2.arab-erp.com"
COMPANY = "cranes company"
MASTERS = ("Company", "Account", "Cost Center", "Warehouse", "Employee", "Customer", "Supplier", "Item", "Crane", "Crane Driver", "Expense Entry Type", "Mode of Payment")
TRANSACTIONS = (
    "Payment Entry", "GL Entry", "Journal Entry", "Payment Ledger Entry",
    "Sales Invoice", "Purchase Invoice", "Expense Entry", "Treasury Transaction", "Crane Profit Settlement",
    "Crane Assignment", "Lead", "Opportunity", "Task", "Project",
    "Sales Order", "Purchase Order", "Delivery Note", "Purchase Receipt", "Stock Entry", "Stock Ledger Entry",
)


def reset_plan():
    _check_development_scope()
    targets = {}
    for doctype in TRANSACTIONS:
        if frappe.db.exists("DocType", doctype) and frappe.get_meta(doctype).has_field("company"):
            targets[doctype] = sorted(frappe.get_all(doctype, filters={"company": COMPANY}, pluck="name"))
    assignments = targets.get("Crane Assignment", [])
    invoices = targets.get("Sales Invoice", [])
    purchases = targets.get("Purchase Invoice", [])
    sheets = set()
    for key, values in (("assignment", assignments), ("sales_invoice", invoices), ("purchase_invoice", purchases)):
        if values:
            sheets.update(frappe.get_all("Crane Timesheet", filters={key: ["in", values]}, pluck="name"))
    targets["Crane Timesheet"] = sorted(sheets)
    expenses = targets.get("Expense Entry", [])
    expense_types = frappe.get_all("Expense Entry Type", filters={"company": COMPANY}, pluck="name")
    account_names = frappe.get_all("Account", filters={"company": COMPANY}, pluck="name")
    maintenance = set()
    for key, values in (("expense_entry", expenses), ("expense_type", expense_types), ("credit_account", account_names)):
        if values:
            maintenance.update(frappe.get_all("Crane Maintenance", filters={key: ["in", values]}, pluck="name"))
    targets["Crane Maintenance"] = sorted(maintenance)
    masters = {dt: sorted(frappe.get_all(dt, pluck="name")) for dt in MASTERS}
    other_ledger = frappe.db.sql("""select name, company, account, debit, credit from `tabGL Entry`
        where company != %s order by name""", (COMPANY,), as_dict=True)
    fingerprint = hashlib.sha256(json.dumps(targets, sort_keys=True).encode()).hexdigest()
    return dict(site=SITE, company=COMPANY, targets=targets, fingerprint=fingerprint,
                counts={dt: len(names) for dt, names in targets.items()}, masters=masters, other_ledger=other_ledger)


def reset_company(backup_path, expected_fingerprint):
    """Caller must have obtained approval for this exact development company."""
    _check_development_scope()
    backup = Path(backup_path).resolve()
    backup_root = Path(frappe.get_site_path("private", "backups")).resolve()
    if backup.parent != backup_root or not backup.name.endswith("-database.sql.gz"):
        raise ValueError("Use a database backup from this development site's backup directory")
    with gzip.open(backup, "rb") as stream:
        if not stream.read(4096):
            raise ValueError("Empty backup")
    plan = reset_plan()
    if plan["fingerprint"] != expected_fingerprint:
        raise ValueError("Company transactions changed since the deletion plan was prepared")
    from erpnext.setup.doctype.transaction_deletion_record.transaction_deletion_record import TransactionDeletionRecord

    cleanup = TransactionDeletionRecord({"doctype": "Transaction Deletion Record", "company": COMPANY})
    frappe.db.savepoint("her_development_reset")
    try:
        for doctype, names in plan["targets"].items():
            if not names:
                continue
            cleanup.delete_version_log(doctype, names)
            cleanup.delete_communications(doctype, names)
            cleanup.delete_comments(doctype, names)
            cleanup.unlink_attachments(doctype, names)
            # Meta includes app-owned Custom Field child tables as well.
            for field in frappe.get_meta(doctype).get_table_fields():
                frappe.db.delete(field.options, {"parenttype": doctype, "parent": ["in", names]})
            cleanup.delete_docs_linked_with_specified_company(doctype, names)
        for doctype, names in plan["targets"].items():
            if names and frappe.db.count(doctype, {"name": ["in", names]}):
                raise AssertionError("Transactions remain in " + doctype)
        for doctype, names in plan["masters"].items():
            if sorted(frappe.get_all(doctype, pluck="name")) != names:
                raise AssertionError("Master data changed: " + doctype)
        after = frappe.db.sql("""select name, company, account, debit, credit from `tabGL Entry`
            where company != %s order by name""", (COMPANY,), as_dict=True)
        if after != plan["other_ledger"]:
            raise AssertionError("Another company's ledger changed")
        if frappe.db.count("GL Entry", {"company": COMPANY}):
            raise AssertionError("Company ledger was not cleared")
        frappe.db.set_value("Company", COMPANY, {"total_monthly_sales": 0, "sales_monthly_history": None})
    except Exception:
        frappe.db.rollback(save_point="her_development_reset")
        raise
    frappe.clear_cache()
    return dict(site=SITE, company=COMPANY, deleted=plan["counts"], fingerprint=plan["fingerprint"],
                backup=str(backup), backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
                master_data_preserved=True, other_company_ledgers_preserved=True)


def _check_development_scope():
    frappe.only_for("System Manager")
    if frappe.local.site != SITE or not frappe.conf.developer_mode:
        raise ValueError("This reset is restricted to the approved development site")
