import frappe
from frappe import _


def payment_account(mode_of_payment, company):
	if not mode_of_payment:
		frappe.throw(_("Select a Mode of Payment before posting the expense."))
	if not frappe.db.get_value("Mode of Payment", mode_of_payment, "enabled"):
		frappe.throw(_("Select an enabled Mode of Payment."))
	account = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "parenttype": "Mode of Payment", "company": company},
		"default_account",
	)
	if not account:
		frappe.throw(
			_("Set a Default Account for Company {0} on Mode of Payment {1}.").format(
				company, mode_of_payment
			)
		)
	return account
