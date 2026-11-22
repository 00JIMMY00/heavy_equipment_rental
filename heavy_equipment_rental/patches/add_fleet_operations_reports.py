from heavy_equipment_rental.workspace import add_workspace_report


def execute():
	for report, reference, key in (
		("Maintenance and Downtime", "Crane Maintenance", "her_maintenance_report_v1"),
		("Fleet Utilization and Availability", "Crane", "her_utilization_report_v1"),
	):
		add_workspace_report(report, reference, key, "Operational Reports")
