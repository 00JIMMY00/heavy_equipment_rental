app_name = "heavy_equipment_rental"
app_title = "Heavy Equipment Rental"
app_publisher = "jimmy"
app_description = "Crane assignments, timesheets, maintenance and direct invoicing"
app_email = "j@gmail.com"
app_license = "mit"
app_logo_url = "/assets/heavy_equipment_rental/branding/mobile-crane-logo.png"
app_include_css = [
	"/assets/heavy_equipment_rental/css/crane_availability.css",
	"/assets/heavy_equipment_rental/css/industrial_tokens.css",
	"/assets/heavy_equipment_rental/css/industrial_desk.css",
	"/assets/heavy_equipment_rental/css/industrial_loading.css",
]
web_include_css = [
	"/assets/heavy_equipment_rental/css/industrial_tokens.css",
	"/assets/heavy_equipment_rental/css/industrial_loading.css",
	"/assets/heavy_equipment_rental/css/industrial_web.css",
]
web_include_js = ["/assets/heavy_equipment_rental/js/industrial_login.js"]
website_context = {
	"favicon": "/assets/heavy_equipment_rental/branding/favicon.ico",
	"splash_image": "/assets/heavy_equipment_rental/branding/loader.gif",
}
required_apps = ["erpnext", "arab_erp_theme"]
after_install = ["heavy_equipment_rental.setup.execute", "heavy_equipment_rental.branding.apply_branding"]
after_migrate = ["heavy_equipment_rental.setup.execute", "heavy_equipment_rental.branding.apply_branding"]

override_doctype_class = {
	"Expense Entry": "heavy_equipment_rental.expenses.RentalExpenseEntry",
	"Journal Entry": "heavy_equipment_rental.expenses.RentalJournalEntry",
}

doc_events = {
    "Shareholder": {"validate": "heavy_equipment_rental.partner_accounts.validate_shareholder"},
	"Crane Timesheet": {
		"before_submit": "heavy_equipment_rental.timesheet_settlement.guard_timesheet",
		"before_cancel": "heavy_equipment_rental.timesheet_settlement.guard_timesheet",
		"on_submit": "heavy_equipment_rental.timesheet_settlement.ensure_settlement",
	},
	"Payment Entry": {
		"validate": "heavy_equipment_rental.partner_reporting.validate_payment",
		"before_submit": "heavy_equipment_rental.partner_reporting.lock_payment_settlements",
	},
	"Purchase Invoice": {
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"on_cancel": "heavy_equipment_rental.purchasing.allow_timesheet_invoice_cancel",
	},
	"Expense Entry": {
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
	},
	"Journal Entry": {
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": [
			"heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction.guard_journal_cancel",
			"heavy_equipment_rental.profit_sharing.guard_closed_period",
		],
	},
	"Sales Invoice": {
		"on_submit": "heavy_equipment_rental.timesheet_settlement.invoice_submitted",
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
	},
}


website_route_rules = [
    {"from_route": "/rental-calendar", "to_route": "rental_calendar"},
    {"from_route": "/rental-calendar/<path:app_path>", "to_route": "rental_calendar"},
]
