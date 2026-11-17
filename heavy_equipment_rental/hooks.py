app_name = "heavy_equipment_rental"
app_title = "Heavy Equipment Rental"
app_publisher = "jimmy"
app_description = "Crane assignments, timesheets, maintenance and direct invoicing"
app_email = "j@gmail.com"
app_license = "mit"
app_logo_url = "/assets/heavy_equipment_rental/branding/mobile-crane-logo.png"
app_include_css = [
	"/assets/heavy_equipment_rental/css/crane_availability.css",
	"/assets/heavy_equipment_rental/css/industrial_tokens.css?v=20261116-panorama-v2",
	"/assets/heavy_equipment_rental/css/industrial_desk.css?v=20261116-ownership-bar-1",
	"/assets/heavy_equipment_rental/css/operations_workspace.css?v=20261117-payment-green",
	"/assets/heavy_equipment_rental/css/industrial_loading.css",
]
web_include_css = [
	"/assets/heavy_equipment_rental/css/industrial_tokens.css?v=20261116-panorama-v2",
	"/assets/heavy_equipment_rental/css/industrial_loading.css",
	"/assets/heavy_equipment_rental/css/industrial_web.css?v=20261116-login-light-4",
]
web_include_js = ["/assets/heavy_equipment_rental/js/industrial_login.js?v=20261116-login-light-4"]
website_context = {
	"favicon": "/assets/heavy_equipment_rental/branding/favicon.ico",
	"splash_image": "/assets/heavy_equipment_rental/branding/loader.gif",
}
required_apps = ["erpnext", "arab_erp_theme"]
after_install = ["heavy_equipment_rental.setup.execute", "heavy_equipment_rental.branding.apply_branding"]
after_migrate = ["heavy_equipment_rental.setup.execute", "heavy_equipment_rental.branding.apply_branding"]

override_doctype_class = {
	"Report": "heavy_equipment_rental.general_ledger.RentalReport",
	"Payment Entry": "heavy_equipment_rental.partner_payment.PartnerPaymentEntry",
	"Asset Repair": "heavy_equipment_rental.asset_repair.RentalAssetRepair",
	"Expense Entry": "heavy_equipment_rental.expenses.RentalExpenseEntry",
	"Journal Entry": "heavy_equipment_rental.expenses.RentalJournalEntry",
}

doc_events = {
    "Company": {"on_update": "heavy_equipment_rental.consolidated_expenses_setup.company_updated"},
    "Stock Entry": {
        "validate": "heavy_equipment_rental.crane_repairs.validate_native_document",
        "before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
        "before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
    },
    "Asset Repair": {
        "validate": "heavy_equipment_rental.crane_repairs.validate_native_document",
        "before_submit": "heavy_equipment_rental.crane_repairs.guard_repair_posting",
        "before_cancel": "heavy_equipment_rental.crane_repairs.guard_repair_posting",
    },
	"Asset": {"validate": "heavy_equipment_rental.crane_assets.validate_linked_asset"},
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
		"validate": "heavy_equipment_rental.crane_repairs.validate_native_document",
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"on_cancel": "heavy_equipment_rental.purchasing.allow_timesheet_invoice_cancel",
		"on_trash": "heavy_equipment_rental.purchasing.unlink_deleted_timesheet_invoice",
	},
	"Expense Entry": {
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
	},
	"Journal Entry": {
		"validate": "heavy_equipment_rental.crane_repairs.attribute_depreciation",
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": [
			"heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction.guard_journal_cancel",
			"heavy_equipment_rental.profit_sharing.guard_closed_period",
		],
	},
	"Sales Invoice": {
		"validate": "heavy_equipment_rental.crane_repairs.validate_native_document",
		"on_submit": "heavy_equipment_rental.timesheet_settlement.invoice_submitted",
		"on_cancel": "heavy_equipment_rental.purchasing.allow_timesheet_invoice_cancel",
		"on_trash": "heavy_equipment_rental.purchasing.unlink_deleted_timesheet_invoice",
		"before_submit": "heavy_equipment_rental.profit_sharing.guard_closed_period",
		"before_cancel": "heavy_equipment_rental.profit_sharing.guard_closed_period",
	},
}


website_route_rules = [
    {"from_route": "/rental-calendar", "to_route": "rental_calendar"},
    {"from_route": "/rental-calendar/<path:app_path>", "to_route": "rental_calendar"},
]


doctype_js = {
    "Expense Entry": "public/js/rental_expense.js",
    "Payment Entry": "public/js/partner_payment.js",
}

app_include_js = ["/assets/heavy_equipment_rental/js/operations_workspace.js?v=20261117-workspace-rail", "/assets/heavy_equipment_rental/js/rental_cancellation.js?v=20261114-cancel-all"]


override_whitelisted_methods = {
    "frappe.desk.query_report.get_script": "heavy_equipment_rental.general_ledger.get_script",
}

app_include_js.append("/assets/heavy_equipment_rental/js/employee_entry.js?v=20261117-1")

before_request = [
    "heavy_equipment_rental.entry_redirect.redirect_crane_operations_entry",
    "heavy_equipment_rental.login_presentation.set_login_language",
]
