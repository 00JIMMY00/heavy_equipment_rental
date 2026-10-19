from frappe import _


def get_data():
	return {
		"fieldname": "project",
		"non_standard_fieldnames": {"Sales Invoice": "name"},
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["Crane Assignment", "Crane Timesheet", "Expense Entry", "Sales Invoice", "Crane Maintenance"],
			},
		],
	}
