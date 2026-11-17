import frappe
from werkzeug.exceptions import abort
from werkzeug.utils import redirect


def redirect_crane_operations_entry():
    request = frappe.local.request
    if (
        request.method in {"GET", "HEAD"}
        and request.path in {"/", "/app", "/app/"}
        and not frappe.form_dict.get("cmd")
    ):
        abort(redirect("/app/crane-operations", code=302))
