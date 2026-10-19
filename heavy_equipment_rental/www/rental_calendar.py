"""Boot context for the rental calendar frontend."""

from urllib.parse import quote

import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        path = frappe.local.request.path
        destination = path if path.startswith("/rental-calendar") else "/rental-calendar"
        frappe.local.flags.redirect_location = f"/login?redirect-to={quote(destination, safe='/')}"
        raise frappe.Redirect
    context.boot = {
        "csrf_token": frappe.sessions.get_csrf_token(),
        "user": frappe.session.user,
    }
