app_name = "heavy_equipment_rental"
app_title = "Heavy Equipment Rental"
app_publisher = "jimmy"
app_description = "Crane assignments, timesheets, maintenance and direct invoicing"
app_email = "j@gmail.com"
app_license = "mit"
app_include_css = ["/assets/heavy_equipment_rental/css/crane_availability.css"]
required_apps = ["erpnext", "arab_erp_theme"]
after_install = "heavy_equipment_rental.setup.execute"
after_migrate = "heavy_equipment_rental.setup.execute"

doc_events = {
	"Journal Entry": {
		"on_cancel": "heavy_equipment_rental.billing.clear_direct_driver_payment_link",
	},
	"Sales Invoice": {
		"before_save": "heavy_equipment_rental.billing.set_invoice_driver_shares",
		"before_submit": "heavy_equipment_rental.billing.set_invoice_driver_shares",
		"before_cancel": "heavy_equipment_rental.billing.guard_direct_driver_payment_cancel",
	},
}

doctype_js = {
	"Sales Invoice": "public/js/crane_sales_invoice.js",
}


website_route_rules = [
    {"from_route": "/rental-calendar", "to_route": "rental_calendar"},
    {"from_route": "/rental-calendar/<path:app_path>", "to_route": "rental_calendar"},
]
