app_name = "heavy_equipment_rental"
app_title = "Heavy Equipment Rental"
app_publisher = "jimmy"
app_description = "Heavy equipment rental projects, fleet reservations and driver timesheets"
app_email = "j@gmail.com"
app_license = "mit"
required_apps = ["erpnext"]
after_install = "heavy_equipment_rental.patches.default_rental_workspace.execute"
after_migrate = "heavy_equipment_rental.patches.default_rental_workspace.execute"

doc_events = {
	"Journal Entry": {
		"before_cancel": "heavy_equipment_rental.heavy_equipment_rental.doctype.expense_entry.expense_entry.guard_journal_entry_cancel"
	}
}

fixtures = [
	{"doctype": "Expense Type", "filters": [["name", "=", "EXT-MAINTENANCE"]]},
	{"doctype": "Custom HTML Block", "filters": [["name", "=", "Crane Operations Overview"]]},
]

