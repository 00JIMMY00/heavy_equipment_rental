app_name = "jimmy_cranes"
app_title = "Jimmy Cranes"
app_publisher = "jimmy"
app_description = "Crane projects, fleet reservations and operator timesheets"
app_email = "j@gmail.com"
app_license = "mit"
required_apps = ["erpnext"]

# Extend native Project with booking guards; no status cascades or scheduled transitions.
doc_events = {
	"Project": {
		"before_validate": "jimmy_cranes.project_events.before_validate",
		"validate": "jimmy_cranes.project_events.validate",
		"on_update": "jimmy_cranes.project_events.on_update",
	}
}
doctype_js = {"Project": "public/js/project.js"}
