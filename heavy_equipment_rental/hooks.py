app_name = "heavy_equipment_rental"
app_title = "Heavy Equipment Rental"
app_publisher = "jimmy"
app_description = "Heavy equipment rental projects, fleet reservations and driver timesheets"
app_email = "j@gmail.com"
app_license = "mit"
required_apps = ["erpnext"]
after_install = "heavy_equipment_rental.setup.execute"
after_migrate = "heavy_equipment_rental.setup.execute"

doc_events = {
	"Journal Entry": {
		"before_cancel": "heavy_equipment_rental.heavy_equipment_rental.doctype.expense_entry.expense_entry.guard_journal_entry_cancel",
		"on_cancel": "heavy_equipment_rental.billing.clear_direct_driver_payment_link",
	},
	"Sales Invoice": {
		"before_save": "heavy_equipment_rental.billing.set_invoice_driver_shares",
		"before_submit": "heavy_equipment_rental.billing.set_invoice_driver_shares",
		"before_cancel": "heavy_equipment_rental.billing.guard_direct_driver_payment_cancel",
	},
}

fixtures = [
	{"doctype": "Expense Type", "filters": [["name", "=", "EXT-MAINTENANCE"]]},
	{"doctype": "Custom HTML Block", "filters": [["name", "=", "Crane Operations Overview"]]},
]

doctype_js = {
	"Sales Invoice": "public/js/crane_sales_invoice.js",
}


website_route_rules = [
    {"from_route": "/rental-calendar", "to_route": "rental_calendar"},
    {"from_route": "/rental-calendar/<path:app_path>", "to_route": "rental_calendar"},
]
