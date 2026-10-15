from frappe import _


def get_data():
	return {
		"fieldname": "project",
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["Crane Assignment", "Crane Timesheet", "Expense Entry"],
			},
		],
	}
