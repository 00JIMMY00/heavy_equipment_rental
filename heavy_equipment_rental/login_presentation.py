"""Request-scoped language for HER's public login, without changing user settings."""

import frappe


def set_login_language():
	request = getattr(frappe.local, "request", None)
	if (
		request
		and request.method == "GET"
		and request.path.rstrip("/") == "/login"
		and frappe.session.user == "Guest"
		and not frappe.form_dict.get("_lang")
	):
		frappe.local.lang = "ar"
