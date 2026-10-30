from frappe import _


def get_data():
    return {
        "fieldname": "amended_from",
        "internal_links": {
            "Crane Assignment": "assignment",
            "Crane": "crane",
            "Customer": "customer",
            "Sales Invoice": "sales_invoice",
            "Purchase Invoice": "purchase_invoice",
            "Crane Timesheet": "amended_from",
        },
        "transactions": [
            {"label": _("Rental"), "items": ["Crane Assignment", "Crane", "Customer"]},
            {"label": _("Documents"), "items": ["Sales Invoice", "Purchase Invoice", "Crane Timesheet"]},
        ],
    }
