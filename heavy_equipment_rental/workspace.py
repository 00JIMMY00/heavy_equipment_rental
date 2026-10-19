"""Synchronize the app-owned Crane Operations workspace."""

import json
from pathlib import Path

import frappe


WORKSPACE_FILE = Path(__file__).resolve().parent / "heavy_equipment_rental/workspace/crane_operations/crane_operations.json"


def sync_operations_workspace():
    if not frappe.db.exists("Workspace", "Crane Operations"):
        return

    source = json.loads(WORKSPACE_FILE.read_text())
    workspace = frappe.get_doc("Workspace", "Crane Operations")
    workspace.content = source["content"]
    workspace.set("shortcuts", source["shortcuts"])
    workspace.set("custom_blocks", [])

    was_in_patch = frappe.flags.in_patch
    frappe.flags.in_patch = True  # Do not export site state over the checked-in layout.
    try:
        workspace.save(ignore_permissions=True)
        for doctype, name in (
            ("Custom HTML Block", "Crane Operations Overview"),
            ("Page", "crane-dashboard"),
        ):
            if frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    finally:
        frappe.flags.in_patch = was_in_patch
    frappe.clear_cache()
