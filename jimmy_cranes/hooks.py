app_name = "jimmy_cranes"
app_title = "Jimmy Cranes"
app_publisher = "jimmy"
app_description = "Crane projects, fleet reservations and operator timesheets"
app_email = "j@gmail.com"
app_license = "mit"
required_apps = ["erpnext"]

# Rental Projects are independent. No ERPNext Project/Timesheet overrides.
before_migrate = "jimmy_cranes.migration.preflight"
after_install = "jimmy_cranes.migration.migrate_existing"
after_migrate = "jimmy_cranes.migration.migrate_existing"
scheduler_events = {"daily": ["jimmy_cranes.rental_operations.start_scheduled_projects"]}
