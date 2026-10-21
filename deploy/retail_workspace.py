"""Create the site-specific El Sakr retail workspace through the Frappe REST API.

The client site does not install heavy_equipment_rental. Keep credentials outside
the repository: set FRAPPE_API_KEY and FRAPPE_API_SECRET, or enter them at prompts.
"""

import argparse
import getpass
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


WORKSPACE_NAME = "El Sakr Retail"
BLOCK_NAME = "El Sakr Retail Overview"
ASSETS = Path(__file__).with_name("retail_workspace")

SECTIONS = [
    ("Daily work · العمل اليومي", [
        ("New Sales Invoice", "DocType", "Sales Invoice", "New"),
        ("Sales Invoices", "DocType", "Sales Invoice", "List"),
        ("New Purchase Invoice", "DocType", "Purchase Invoice", "New"),
        ("Purchase Invoices", "DocType", "Purchase Invoice", "List"),
        ("Record Payment", "DocType", "Payment Entry", "New"),
        ("Payment Entries", "DocType", "Payment Entry", "List"),
    ]),
    ("People & products · العملاء والمنتجات", [
        ("Customers", "DocType", "Customer", "List"),
        ("Suppliers", "DocType", "Supplier", "List"),
        ("Items", "DocType", "Item", "List"),
        ("Item Prices", "DocType", "Item Price", "List"),
    ]),
    ("Receivables & payables · المستحقات", [
        ("Accounts Receivable", "Report", "Accounts Receivable", None),
        ("Accounts Payable", "Report", "Accounts Payable", None),
        ("Customer Ledger Summary", "Report", "Customer Ledger Summary", None),
        ("Supplier Ledger Summary", "Report", "Supplier Ledger Summary", None),
        ("Payment Ledger", "Report", "Payment Ledger", None),
    ]),
    ("Sales reports · تقارير المبيعات", [
        ("Sales Register", "Report", "Sales Register", None),
        ("Item-wise Sales Register", "Report", "Item-wise Sales Register", None),
        ("Sales Invoice Trends", "Report", "Sales Invoice Trends", None),
        ("Sales Analytics", "Report", "Sales Analytics", None),
        ("Gross Profit", "Report", "Gross Profit", None),
    ]),
    ("Purchase reports · تقارير المشتريات", [
        ("Purchase Register", "Report", "Purchase Register", None),
        ("Item-wise Purchase Register", "Report", "Item-wise Purchase Register", None),
        ("Purchase Invoice Trends", "Report", "Purchase Invoice Trends", None),
        ("Purchase Analytics", "Report", "Purchase Analytics", None),
    ]),
    ("Stock reports · تقارير المخزون", [
        ("Stock Balance", "Report", "Stock Balance", None),
        ("Stock Ledger", "Report", "Stock Ledger", None),
    ]),
]

ROLES = [
    "Accounts User", "Accounts Manager", "Sales User", "Sales Manager",
    "Purchase User", "Purchase Manager", "Stock User", "Stock Manager",
    "System Manager",
]


class FrappeAPI:
    def __init__(self, site, key, secret):
        self.site = site.rstrip("/")
        self.headers = {
            "Authorization": f"token {key}:{secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "curl/8.5.0",
        }

    def request(self, method, path, payload=None, params=None, allow_404=False):
        url = self.site + path
        if params:
            url += "?" + urlencode(params)
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = Request(url, data=data, headers=self.headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if allow_404 and error.code == 404:
                return None
            detail = error.read().decode("utf-8", "replace")[:800]
            raise RuntimeError(f"{method} {path}: HTTP {error.code}: {detail}") from None

    def resource(self, doctype, name):
        return f"/api/resource/{quote(doctype, safe='')}/{quote(name, safe='')}"

    def list_names(self, doctype, names):
        result = self.request("GET", f"/api/resource/{quote(doctype, safe='')}", params={
            "fields": '["name"]',
            "filters": json.dumps([["name", "in", names]]),
            "limit_page_length": len(names) + 1,
        })
        return {row["name"] for row in result["data"]}

    def upsert(self, doctype, name, values):
        existing = self.request("GET", self.resource(doctype, name), allow_404=True)
        if existing:
            self.request("PUT", self.resource(doctype, name), values)
            print(f"Updated {doctype}: {name}")
        else:
            self.request("POST", f"/api/resource/{quote(doctype, safe='')}", {"doctype": doctype, "name": name, **values})
            print(f"Created {doctype}: {name}")


def build_workspace():
    content = [{"id": "retail-overview", "type": "custom_block", "data": {
        "custom_block_name": BLOCK_NAME, "col": 12,
    }}]
    shortcuts = []
    for section_index, (heading, items) in enumerate(SECTIONS):
        content.append({"id": f"retail-section-{section_index}", "type": "header", "data": {
            "text": f'<span class="h4"><b>{heading}</b></span>', "col": 12,
        }})
        for item_index, (label, kind, target, view) in enumerate(items):
            content.append({"id": f"retail-link-{section_index}-{item_index}", "type": "shortcut", "data": {
                "shortcut_name": label, "col": 3,
            }})
            shortcut = {"label": label, "type": kind, "link_to": target}
            if view:
                shortcut["doc_view"] = view
            shortcuts.append(shortcut)
    return {
        "title": WORKSPACE_NAME,
        "label": WORKSPACE_NAME,
        "module": "Accounts",
        "public": 1,
        "is_hidden": 0,
        "icon": "sell",
        "sequence_id": 3,
        "content": json.dumps(content, ensure_ascii=False),
        "shortcuts": shortcuts,
        "custom_blocks": [{"custom_block_name": BLOCK_NAME, "label": BLOCK_NAME}],
        "roles": [{"role": role} for role in ROLES],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="https://elsakr.arab-erp.com")
    args = parser.parse_args()
    key = os.environ.get("FRAPPE_API_KEY") or getpass.getpass("Frappe API key: ")
    secret = os.environ.get("FRAPPE_API_SECRET") or getpass.getpass("Frappe API secret: ")
    api = FrappeAPI(args.site, key, secret)

    companies = api.request("GET", "/api/resource/Company", params={
        "fields": '["name","default_currency"]', "limit_page_length": 20,
    })["data"]
    if len(companies) != 1:
        raise RuntimeError("Expected exactly one company; select a company before publishing this workspace")
    company = companies[0]
    if not company["default_currency"]:
        raise RuntimeError("The company needs a default currency")

    items = [item for _, section in SECTIONS for item in section]
    for kind in ("DocType", "Report"):
        required = {target for _, item_kind, target, _ in items if item_kind == kind}
        missing = required - api.list_names(kind, sorted(required))
        if missing:
            raise RuntimeError(f"Missing {kind} records: {', '.join(sorted(missing))}")
    missing_roles = set(ROLES) - api.list_names("Role", ROLES)
    if missing_roles:
        raise RuntimeError(f"Missing roles: {', '.join(sorted(missing_roles))}")

    script = (ASSETS / "overview.js").read_text()
    script = script.replace("__COMPANY_JSON__", json.dumps(company["name"], ensure_ascii=False))
    script = script.replace("__CURRENCY_JSON__", json.dumps(company["default_currency"], ensure_ascii=False))
    api.upsert("Custom HTML Block", BLOCK_NAME, {
        "html": (ASSETS / "overview.html").read_text(),
        "style": (ASSETS / "overview.css").read_text(),
        "script": script,
        "private": 0,
        "roles": [],
    })
    api.upsert("Workspace", WORKSPACE_NAME, build_workspace())
    print(f"Workspace: {args.site.rstrip('/')}/app/el-sakr-retail")


if __name__ == "__main__":
    main()
