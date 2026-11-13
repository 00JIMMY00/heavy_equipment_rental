"""Backfill identities and links, preserving submitted journals and agreement snapshots."""

import json

import frappe

from heavy_equipment_rental.partner_accounts import default_account, install, shareholder_for_supplier


def execute():
    install()
    for share in frappe.get_all("Crane Settlement Share", filters={"is_company": 0, "supplier": ["is", "set"]},
            fields=["name", "parent", "shareholder", "supplier", "ledger_party_type"]):
        if not share.shareholder:
            company = frappe.db.get_value("Crane Profit Settlement", share.parent, "company")
            if company:
                frappe.db.set_value("Crane Settlement Share", share.name, dict(
                    shareholder=shareholder_for_supplier(share.supplier, company), ledger_party_type="Supplier"), update_modified=False)
    for crane in frappe.get_all("Crane", filters={"sharing_company": ["is", "set"]},
            fields=["name", "sharing_company", "operating_partner", "operating_shareholder", "partner_payable_account"]):
        for row in frappe.get_all("Crane Partner", filters={"parent": crane.name, "parenttype": "Crane"},
                fields=["name", "is_company", "supplier", "shareholder"]):
            if not row.is_company and row.supplier and not row.shareholder:
                frappe.db.set_value("Crane Partner", row.name, "shareholder",
                    shareholder_for_supplier(row.supplier, crane.sharing_company), update_modified=False)
        if crane.operating_partner and not crane.operating_shareholder:
            frappe.db.set_value("Crane", crane.name, "operating_shareholder",
                shareholder_for_supplier(crane.operating_partner, crane.sharing_company), update_modified=False)
        trade_payable = frappe.get_cached_value("Company", crane.sharing_company, "default_payable_account")
        if not crane.partner_payable_account or crane.partner_payable_account == trade_payable:
            frappe.db.set_value("Crane", crane.name, "partner_payable_account",
                default_account(crane.sharing_company), update_modified=False)
    for settlement in frappe.get_all("Crane Profit Settlement", filters={"docstatus": 1},
            fields=["name", "crane", "timesheet", "source_snapshot"]):
        invoices = {s["name"] for s in json.loads(settlement.source_snapshot or "[]") if s["doctype"] == "Sales Invoice"}
        if not invoices:
            continue
        sheets = frappe.get_all("Crane Timesheet", filters={"crane": settlement.crane, "docstatus": 1,
            "sales_invoice": ["in", list(invoices)]}, fields=["name", "sales_invoice", "profit_settlement"])
        for sheet in sheets:
            if not sheet.profit_settlement:
                frappe.db.set_value("Crane Timesheet", sheet.name, "profit_settlement", settlement.name, update_modified=False)
        if len(sheets) == 1 and not settlement.timesheet:
            # A historical period remains a period closure even when its single Timesheet is displayed.
            frappe.db.set_value("Crane Profit Settlement", settlement.name,
                dict(timesheet=sheets[0].name, sales_invoice=sheets[0].sales_invoice, settlement_basis="Period"), update_modified=False)
