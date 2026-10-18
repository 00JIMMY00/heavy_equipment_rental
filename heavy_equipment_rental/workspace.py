"""Keep the rental calendar shortcuts in the app's operations workspace."""

import json

import frappe


CALENDARS = (
    ("rental-calendar-link", "تقويم الحجوزات", "/rental-calendar"),
    ("resource-calendar-link", "تقويم الموارد", "/rental-calendar/timeline"),
)


def sync_calendar_shortcuts():
    if not frappe.db.exists("Workspace", "Crane Operations"):
        return

    workspace = frappe.get_doc("Workspace", "Crane Operations")
    content = json.loads(workspace.content or "[]")
    content = [
        item for item in content
        if item.get("data", {}).get("shortcut_name") != "حجوزات الأسطول"
    ]
    names = {item.get("data", {}).get("shortcut_name") for item in content}
    insert_at = next(
        (index + 1 for index, item in enumerate(content) if item.get("id") == "crane-dashboard-link"),
        len(content),
    )
    for tile_id, label, _url in CALENDARS:
        if label not in names:
            content.insert(insert_at, {
                "id": tile_id, "type": "shortcut", "data": {"shortcut_name": label, "col": 6},
            })
            insert_at += 1
        else:
            for item in content:
                if item.get("data", {}).get("shortcut_name") == label:
                    item["data"]["col"] = 6

    for shortcut in list(workspace.shortcuts):
        if shortcut.link_to == "crane-project-gantt":
            workspace.remove(shortcut)
    for _tile_id, label, url in CALENDARS:
        shortcut = next((item for item in workspace.shortcuts if item.label == label), None)
        if shortcut:
            shortcut.type = "URL"
            shortcut.url = url
            shortcut.link_to = None
        else:
            workspace.append("shortcuts", {"label": label, "type": "URL", "url": url})

    workspace.content = json.dumps(content, ensure_ascii=False)
    was_in_patch = frappe.flags.in_patch
    frappe.flags.in_patch = True  # Keep the checked-in workspace file authoritative.
    try:
        workspace.save(ignore_permissions=True)
    finally:
        frappe.flags.in_patch = was_in_patch
    frappe.clear_cache()
