"""Archive obsolete hired-crane Asset links while preserving the native Asset ledger."""
import json

import frappe


def execute():
    for row in frappe.get_all("Crane", filters={"hired_from_supplier": 1},
                              fields=["name", "asset", "ownership_type", "asset_accounting_basis", "legacy_asset_recognition"]):
        if not row.asset and not row.asset_accounting_basis:
            continue
        values = {"asset_accounting_basis": ""}
        if row.asset:
            history = json.loads(row.legacy_asset_recognition or "[]")
            history.append(dict(asset=row.asset, basis=row.asset_accounting_basis,
                                ownership_type=row.ownership_type, reason="Hired from Supplier"))
            values.update(asset=None, legacy_asset_recognition=json.dumps(history))
        frappe.db.set_value("Crane", row.name, values, update_modified=False)
