"""Restore pre-550f4f5d terms prospectively; preserve historical accounting."""

import json

import frappe
from frappe.utils import add_days, getdate, today

RESTORED_TERMS = dict(settlement_approval="On Invoice Submission",
	distribution_posting="Source Revenue Accounts", settlement_revenue_basis="Invoice Grand Total",
	include_depreciation=0)


def execute():
	for name in frappe.get_all("Crane", pluck="name"):
		crane = frappe.get_doc("Crane", name)
		if all(crane.get(key) == value for key, value in RESTORED_TERMS.items()):
			continue
		history = json.loads(crane.agreement_history or "[]")
		if not history:
			frappe.db.set_value("Crane", name, RESTORED_TERMS, update_modified=False)
			continue
		# Legacy Net Profit remains immutable until an explicit contractual change.
		if crane.sharing_calculation == "Legacy Net Profit" or not history[-1].get("effective_from"):
			continue
		last_date = frappe.db.get_value("Crane Profit Settlement",
			{"crane": name, "docstatus": 1}, "max(to_date)")
		effective = max(getdate(today()), getdate(add_days(history[-1]["effective_from"], 1)))
		if last_date:
			effective = max(effective, getdate(add_days(last_date, 1)))
		crane.update(dict(RESTORED_TERMS, agreement_effective_from=effective))
		crane.save()
		# New controllers record when terms were entered, independently of work dates.
		# Retain the effective date of this one-time historical conversion as well.
		versions = json.loads(crane.agreement_history)
		if len(versions) > len(history) and not versions[-1].get("effective_from"):
			versions[-1]["effective_from"] = str(effective)
			frappe.db.set_value("Crane", name, "agreement_history", json.dumps(versions), update_modified=False)
		crane.add_comment("Info", "Restored automatic source-revenue settlements prospectively from "
			+ str(effective) + ". Previous agreements, settlements, journals and payments are preserved.")
