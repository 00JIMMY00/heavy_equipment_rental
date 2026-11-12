from frappe import _


def get_data():
    return {
        "fieldname": "assignment",
        "internal_links": {
            "Crane": ["assigned_cranes", "crane"],
            "Customer": "customer",
        },
        "non_standard_fieldnames": {"Expense Entry": "crane_assignment"},
        "transactions": [
            {"label": _("Rental"), "items": ["Crane", "Customer", "Crane Timesheet"]},
            {"label": _("Expenses"), "items": ["Expense Entry"]},
        ],
    }
