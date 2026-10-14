"""Backfill project dates and crane completion totals on existing assignments."""

import frappe


def execute():
	frappe.db.sql(
		"""UPDATE `tabCrane Assignment` assignment
		LEFT JOIN `tabCrane Project` project ON project.name = assignment.project
		LEFT JOIN (
			SELECT parent,
				SUM(status = 'Complete') AS completed,
				SUM(status != 'Cancelled') AS total
			FROM `tabAssigned Crane`
			WHERE parenttype = 'Crane Assignment'
			GROUP BY parent
		) cranes ON cranes.parent = assignment.name
		SET assignment.project_start_date = project.expected_start_date,
			assignment.project_end_date = project.expected_end_date,
			assignment.completed_cranes = COALESCE(cranes.completed, 0),
			assignment.total_cranes = COALESCE(cranes.total, 0),
			assignment.completion_percentage = CASE
				WHEN COALESCE(cranes.total, 0) = 0 THEN 0
				ELSE 100 * cranes.completed / cranes.total
			END"""
	)
