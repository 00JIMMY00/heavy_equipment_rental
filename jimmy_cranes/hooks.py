app_name = "jimmy_cranes"
app_title = "Jimmy Cranes"
app_publisher = "jimmy"
app_description = "cranes"
app_email = "j@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "jimmy_cranes",
# 		"logo": "/assets/jimmy_cranes/logo.png",
# 		"title": "Jimmy Cranes",
# 		"route": "/jimmy_cranes",
# 		"has_permission": "jimmy_cranes.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/jimmy_cranes/css/jimmy_cranes.css"
# app_include_js = "/assets/jimmy_cranes/js/jimmy_cranes.js"

# include js, css files in header of web template
# web_include_css = "/assets/jimmy_cranes/css/jimmy_cranes.css"
# web_include_js = "/assets/jimmy_cranes/js/jimmy_cranes.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "jimmy_cranes/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "jimmy_cranes/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "jimmy_cranes.utils.jinja_methods",
# 	"filters": "jimmy_cranes.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "jimmy_cranes.install.before_install"
# after_install = "jimmy_cranes.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "jimmy_cranes.uninstall.before_uninstall"
# after_uninstall = "jimmy_cranes.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "jimmy_cranes.utils.before_app_install"
# after_app_install = "jimmy_cranes.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "jimmy_cranes.utils.before_app_uninstall"
# after_app_uninstall = "jimmy_cranes.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "jimmy_cranes.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["jimmy_cranes.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"jimmy_cranes.tasks.all"
# 	],
# 	"daily": [
# 		"jimmy_cranes.tasks.daily"
# 	],
# 	"hourly": [
# 		"jimmy_cranes.tasks.hourly"
# 	],
# 	"weekly": [
# 		"jimmy_cranes.tasks.weekly"
# 	],
# 	"monthly": [
# 		"jimmy_cranes.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "jimmy_cranes.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "jimmy_cranes.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "jimmy_cranes.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["jimmy_cranes.utils.before_request"]
# after_request = ["jimmy_cranes.utils.after_request"]

# Job Events
# ----------
# before_job = ["jimmy_cranes.utils.before_job"]
# after_job = ["jimmy_cranes.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"jimmy_cranes.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

