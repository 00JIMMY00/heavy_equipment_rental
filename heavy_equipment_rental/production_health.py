"""Read-only release health check, called through Bench (not a public endpoint)."""
import frappe
from pathlib import Path
import json


def check():
    manifest = Path(__file__).resolve().parent.parent / 'deploy/runtime-manifest/apps.json'
    required = {'frappe'} | {app['name'] for app in json.loads(manifest.read_text())['apps']}
    if not required.issubset(frappe.get_installed_apps()):
        raise RuntimeError("Required production apps are missing")
    frappe.db.sql("select 1")
    frappe.cache().ping()
    from frappe.utils.background_jobs import get_redis_conn
    get_redis_conn().ping()
    for doctype in ("Crane", "Rental Contract", "Crane Timesheet", "Grouped Expense"):
        frappe.get_meta(doctype)
        frappe.db.count(doctype)
    return {"status": "ok", "apps": sorted(required)}
