from frappe import _


def get_data():
	return {
		"fieldname": "crane",
		"internal_links": {"Crane Assignment": ["assigned_cranes", "crane"]},
		"non_standard_fieldnames": {"Crane Timesheet": "crane"},
		"transactions": [
			{"label": _("Rental"), "items": ["Crane Assignment", "Crane Timesheet"]},
			{"label": _("Operations"), "items": ["Crane Maintenance", "Expense Entry"]},
		],
	}
