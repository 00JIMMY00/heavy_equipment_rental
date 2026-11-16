from frappe import _


def get_data():
    return {
        "fieldname": "amended_from",
        "non_standard_fieldnames": {"Expense Entry": "crane_timesheet", "Crane Maintenance": "crane_timesheet"},
        "internal_links": {
            "Rental Contract": "assignment",
            "Crane": "crane",
            "Customer": "customer",
            "Sales Invoice": "sales_invoice",
            "Purchase Invoice": "purchase_invoice",
            "Crane Timesheet": "amended_from",
            "Crane Profit Settlement": "profit_settlement",
        },
        "transactions": [
            {"label": _("Operations"), "items": ["Expense Entry", "Crane Maintenance"]},
            {"label": _("Rental"), "items": ["Rental Contract", "Crane", "Customer"]},
            {"label": _("Documents"), "items": ["Sales Invoice", "Purchase Invoice", "Crane Timesheet", "Crane Profit Settlement"]},
        ],
    }
