"""Schema contracts for the simplified booking model."""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRentalSchema(FrappeTestCase):
	def test_crane_project_and_independent_timesheets(self):
		self.assertEqual(frappe.get_meta("Crane Assignment").get_field("project").options, "Crane Project")
		self.assertEqual(frappe.get_meta("Crane Timesheet").get_field("project").options, "Crane Project")
		self.assertTrue(frappe.get_meta("Crane Timesheet").is_submittable)
		self.assertEqual(frappe.get_meta("Crane").get_field("item").options, "Item")
		self.assertEqual(frappe.get_meta("Assigned Crane").get_field("rental_rate_unit").options.splitlines(), ["Hour", "Day", "Month"])
		self.assertEqual(frappe.get_meta("Crane Timesheet").get_field("sales_invoice").options, "Sales Invoice")
		self.assertFalse(frappe.get_meta("Crane Assignment").is_submittable)
		self.assertIsNone(frappe.get_meta("Crane Assignment").get_field("status"))
		self.assertIsNone(frappe.get_meta("Timesheet Entry").get_field("crane"))
		self.assertTrue(frappe.get_meta("Assigned Crane").istable)
		self.assertTrue(frappe.get_meta("Timesheet Entry").istable)
		self.assertEqual(frappe.get_meta("Crane Project").module, "Jimmy Cranes")
		self.assertEqual(frappe.get_meta("Project").module, "Projects")
		self.assertFalse(frappe.get_hooks("doc_events").get("Project"))
		self.assertEqual(frappe.get_meta("Timesheet").module, "Projects")
		self.assertEqual(
			frappe.get_meta("Assigned Crane").get_field("status").options.splitlines(),
			["Draft", "Reserved", "Cancelled"],
		)
		self.assertIsNone(frappe.get_meta("Assigned Crane").get_field("actual_start_date"))
		self.assertIsNone(frappe.get_meta("Assigned Crane").get_field("actual_end_date"))
		self.assertFalse(
			any(
				"jimmy_cranes" in path
				for path in frappe.get_hooks("override_doctype_class").get("Project", [])
			)
		)
