"""Rental voucher tracing inside ERPNext's native General Ledger report."""

import importlib.util

import frappe
from frappe import _
from frappe.core.doctype.report.report import Report
from frappe.desk.query_report import get_script as native_get_script
from erpnext.accounts.report.general_ledger import general_ledger as native_gl


class RentalReport(Report):
    def execute_module(self, filters):
        if self.name == "General Ledger" and (filters.get("crane") or filters.get("cps") or filters.get("consolidated_expense")):
            return execute(frappe._dict(filters))
        return super().execute_module(filters)


@frappe.whitelist()
def get_script(report_name):
    result = native_get_script(report_name)
    if report_name == "General Ledger":
        result["script"] += "\n" + frappe.read_file(frappe.get_app_path(
            "heavy_equipment_rental", "public", "js", "general_ledger.js"))
    return result


def settlement_vouchers(doc):
    result = set()
    if doc.journal_entry:
        result.add(("Journal Entry", doc.journal_entry))
    for source in frappe.parse_json(doc.source_snapshot or "[]"):
        if source.get("doctype") == "Expense Entry":
            journal = source.get("journal") or frappe.db.get_value(
                "Expense Entry", source["name"], "journal_entry")
            if journal:
                result.add(("Journal Entry", journal))
        elif source.get("doctype") and source.get("name"):
            result.add((source["doctype"], source["name"]))
    return result


def voucher_scope(filters):
    if filters.get("consolidated_expense"):
        doc = frappe.get_doc("Grouped Expense", filters.consolidated_expense)
        doc.check_permission("read")
        if doc.company != filters.company or (filters.crane and doc.crane != filters.crane):
            frappe.throw(_("The expense must match the selected Company and Crane."))
        result = set()
        for row in doc.items:
            if row.journal_entry:
                frappe.get_doc("Journal Entry", row.journal_entry).check_permission("read")
                result.add(("Journal Entry", row.journal_entry))
            if row.expense_entry:
                expense = frappe.get_doc("Expense Entry", row.expense_entry)
                expense.check_permission("read")
                if expense.journal_entry:
                    frappe.get_doc("Journal Entry", expense.journal_entry).check_permission("read")
                    result.add(("Journal Entry", expense.journal_entry))
        if filters.cps:
            settlement = frappe.get_doc("Crane Profit Settlement", filters.cps)
            settlement.check_permission("read")
            result &= settlement_vouchers(settlement)
        return result
    if filters.cps:
        doc = frappe.get_doc("Crane Profit Settlement", filters.cps)
        doc.check_permission("read")
        if doc.company != filters.company or (filters.crane and doc.crane != filters.crane):
            frappe.throw(_("The CPS must match the selected Company and Crane."))
        if filters.crane:
            frappe.get_doc("Crane", filters.crane).check_permission("read")
        return settlement_vouchers(doc)

    frappe.get_doc("Crane", filters.crane).check_permission("read")
    result = set()
    # Inspect headers and native voucher child rows carrying HER's Crane link.
    for doctype in ("Sales Invoice", "Purchase Invoice", "Journal Entry", "Stock Entry", "Payment Entry"):
        meta = frappe.get_meta(doctype)
        locations = [doctype] if meta.has_field("crane") else []
        locations.extend(df.options for df in meta.get_table_fields()
                         if frappe.get_meta(df.options).has_field("crane"))
        for location in locations:
            names = frappe.get_all(doctype, filters=[
                [doctype, "company", "=", filters.company],
                [location, "crane", "=", filters.crane],
            ], pluck="name", distinct=True)
            result.update((doctype, name) for name in names)
    for journal in frappe.get_all("Expense Entry", filters={
            "company": filters.company, "crane": filters.crane}, pluck="journal_entry"):
        if journal:
            result.add(("Journal Entry", journal))
    for row in frappe.get_all("Crane Profit Settlement", filters={
            "company": filters.company, "crane": filters.crane},
            fields=["journal_entry", "source_snapshot"]):
        result.update(settlement_vouchers(row))
    return result


def include_payments(vouchers, company):
    """Trace native payment references once, without unrelated invoice siblings."""
    result = set(vouchers)
    by_type = {}
    for doctype, name in vouchers:
        by_type.setdefault(doctype, []).append(name)
    for doctype, names in by_type.items():
        payments = frappe.get_all("Payment Entry", filters=[
            ["Payment Entry", "company", "=", company],
            ["Payment Entry Reference", "reference_doctype", "=", doctype],
            ["Payment Entry Reference", "reference_name", "in", names],
        ], pluck="name", distinct=True)
        result.update(("Payment Entry", name) for name in payments)
    return result


def execute(filters):
    vouchers = sorted(include_payments(voucher_scope(filters), filters.company))
    # Load an isolated native module, retaining ERPNext's grouping, balances,
    # currencies and GL permissions. Never monkey-patch its shared globals:
    # simultaneous requests (and unfiltered reports) must remain independent.
    spec = importlib.util.spec_from_file_location("her_scoped_general_ledger", native_gl.__file__)
    scoped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scoped)
    native_conditions = scoped.get_conditions

    def get_conditions(values):
        conditions = native_conditions(values)
        clauses = []
        by_type = {}
        for doctype, name in vouchers:
            by_type.setdefault(doctype, []).append(name)
        for index, (doctype, names) in enumerate(by_type.items()):
            values[f"her_type_{index}"] = doctype
            values[f"her_names_{index}"] = tuple(names)
            clauses.append(f"(voucher_type = %(her_type_{index})s AND voucher_no IN %(her_names_{index})s)")
        return conditions + " AND (" + (" OR ".join(clauses) if clauses else "1=0") + ")"

    scoped.get_conditions = get_conditions
    columns, rows = scoped.execute(filters)
    return columns, rows, _(
        "Crane/CPS filters show complete linked accounting vouchers, including shared vouchers. "
        "Amounts are not prorated to the CPS. Posting date and other GL filters still apply.")
