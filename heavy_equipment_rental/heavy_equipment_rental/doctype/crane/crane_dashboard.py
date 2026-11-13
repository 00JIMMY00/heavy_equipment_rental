from frappe import _


def get_data():
	return {
		"fieldname": "crane",
		"internal_links": {"Crane Assignment": ["assigned_cranes", "crane"], "Asset": ["asset"]},
		"non_standard_fieldnames": {"Crane Timesheet": "crane"},
		"transactions": [
			{"label": _("Fixed Asset"), "items": ["Asset"]},
			{"label": _("Rental"), "items": ["Crane Assignment", "Crane Timesheet"]},
			{"label": _("Operations"), "items": ["Crane Maintenance", "Expense Entry", "Stock Entry", "Asset Repair"]},
			{"label": _("Profit Sharing"), "items": ["Crane Profit Settlement"]},
		],
	}
