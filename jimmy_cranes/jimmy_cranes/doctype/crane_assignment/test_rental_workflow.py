"""Schema contracts for the simplified booking model."""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRentalSchema(FrappeTestCase):
	def test_native_project_and_independent_timesheets(self):
		self.assertEqual(frappe.get_meta("Crane Assignment").get_field("project").options, "Project")
		self.assertEqual(frappe.get_meta("Crane Timesheet").get_field("project").options, "Project")
		self.assertTrue(frappe.get_meta("Crane Timesheet").is_submittable)
		self.assertFalse(frappe.get_meta("Crane Assignment").is_submittable)
		self.assertIsNone(frappe.get_meta("Crane Assignment").get_field("status"))
		self.assertIsNone(frappe.get_meta("Timesheet Entry").get_field("crane"))
		self.assertTrue(frappe.get_meta("Assigned Crane").istable)
		self.assertTrue(frappe.get_meta("Timesheet Entry").istable)
		self.assertEqual(frappe.get_meta("Project").module, "Projects")
		self.assertEqual(frappe.get_meta("Timesheet").module, "Projects")
		self.assertEqual(
			frappe.get_meta("Assigned Crane").get_field("status").options.splitlines(),
			["Draft", "Reserved", "Released", "Cancelled"],
		)
		self.assertIsNone(frappe.get_meta("Assigned Crane").get_field("actual_start_date"))
		self.assertFalse(
			any(
				"jimmy_cranes" in path
				for path in frappe.get_hooks("override_doctype_class").get("Project", [])
			)
		)
