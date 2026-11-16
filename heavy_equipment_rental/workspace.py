"""Install an editable site-owned workspace once; never reset subsequent edits."""

import json
from pathlib import Path

import frappe


WORKSPACE_FILE = Path(__file__).resolve().parent / "templates/crane_operations.json"
LAYOUT_VERSION_KEY = "her_operations_workspace_layout_v2"


def sync_operations_workspace():
    # The template deliberately lives outside Frappe's standard Workspace sync
    # directory. Site changes must survive both setup and future migrations.
    if frappe.db.get_default(LAYOUT_VERSION_KEY):
        return

    source = json.loads(WORKSPACE_FILE.read_text())
    exists = frappe.db.exists("Workspace", "Crane Operations")
    if exists:
        workspace = frappe.get_doc("Workspace", "Crane Operations")
        backup = Path(frappe.get_site_path("private", "backups", "her-workspace-before-v2.json"))
        backup.parent.mkdir(parents=True, exist_ok=True)
        # Keep the original even if a failed transaction is retried.
        if not backup.exists():
            backup.write_text(frappe.as_json(workspace.as_dict()), encoding="utf-8")
            backup.chmod(0o600)
        workspace.content = source["content"]
        workspace.set("shortcuts", source["shortcuts"])
        workspace.set("links", source["links"])
        # Preserve existing access, charts and custom blocks for the editor.
        # No module means developer-mode edits stay on this site, not in git.
        workspace.module = None
    else:
        workspace = frappe.get_doc(source)

    was_in_patch = frappe.flags.in_patch
    frappe.flags.in_patch = True
    try:
        if exists:
            workspace.save(ignore_permissions=True)
        else:
            workspace.insert(ignore_permissions=True)
        frappe.db.set_default(LAYOUT_VERSION_KEY, "1")
    finally:
        frappe.flags.in_patch = was_in_patch
    frappe.clear_cache()


@frappe.whitelist()
def get_operations_counts():
    """Counts for this workspace's visible DocType links, using user permissions."""
    workspace = frappe.get_doc("Workspace", "Crane Operations")
    workspace.check_permission("read")
    from frappe.desk.desktop import Workspace

    # Apply the same workspace role/module access checks as native Desk.
    visible = Workspace(workspace.as_dict(), minimal=True)
    if not visible.is_permitted():
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
    result = {}
    for row in workspace.links:
        if row.type != "Link" or row.link_type != "DocType" or row.link_to in result:
            continue
        doctype = row.link_to
        if not frappe.has_permission(doctype, "read") or frappe.get_meta(doctype).issingle:
            continue
        result[doctype] = frappe.get_list(
            doctype, fields=["count(name) as total"], limit_page_length=1
        )[0].total
    return result
