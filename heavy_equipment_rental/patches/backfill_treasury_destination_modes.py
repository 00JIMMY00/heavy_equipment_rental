"""Fill the destination mode on drafts with a single matching enabled mode."""

from collections import defaultdict

import frappe


def execute():
    drafts = frappe.get_all("Treasury Transaction", filters={
        "docstatus": 0,
        "destination_account": ["is", "set"],
        "destination_mode_of_payment": ["is", "not set"],
    }, fields=["name", "company", "destination_account"])
    if not drafts:
        return

    matches = defaultdict(set)
    for row in frappe.get_all("Mode of Payment", filters=[
        ["enabled", "=", 1],
        ["Mode of Payment Account", "company", "in", list({draft.company for draft in drafts})],
        ["Mode of Payment Account", "default_account", "in", list({draft.destination_account for draft in drafts})],
    ], fields=["name", "accounts.company", "accounts.default_account"]):
        matches[row.company, row.default_account].add(row.name)

    for draft in drafts:
        modes = matches[draft.company, draft.destination_account]
        if len(modes) == 1:
            frappe.db.set_value("Treasury Transaction", draft.name, "destination_mode_of_payment",
                                next(iter(modes)), update_modified=False)
