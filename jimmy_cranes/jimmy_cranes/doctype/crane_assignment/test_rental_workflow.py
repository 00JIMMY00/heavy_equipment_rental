"""Schema separation and upgrade checks for the independent rental workflow."""

import frappe
from frappe.tests.utils import FrappeTestCase

from jimmy_cranes.migration import migrate_existing


class TestRentalMigration(FrappeTestCase):
	def test_native_doctypes_are_not_overridden(self):
		self.assertEqual(frappe.get_meta("Crane Assignment").get_field("project").options, "Crane Project")
		self.assertEqual(frappe.get_meta("Crane Timesheet").get_field("project").options, "Crane Project")
		self.assertTrue(frappe.get_meta("Crane Timesheet").is_submittable)
		self.assertFalse(frappe.get_meta("Crane Assignment").is_submittable)
		self.assertIsNone(frappe.get_meta("Timesheet Entry").get_field("crane"))
		self.assertEqual(frappe.get_meta("Project").module, "Projects")
		self.assertEqual(frappe.get_meta("Timesheet").module, "Projects")
		self.assertFalse(any("jimmy_cranes" in x for x in frappe.get_hooks("doctype_js").get("Project", [])))

	def test_migration_is_idempotent_and_preserves_history(self):
		before = {
			dt: frappe.get_all(dt, fields=["*"], order_by="name")
			for dt in (
				"Project",
				"Crane Project",
				"Crane Assignment",
				"Assigned Crane",
				"Crane Timesheet",
				"Timesheet Entry",
				"Crane Period Price",
			)
		}
		migrate_existing()
		after = {dt: frappe.get_all(dt, fields=["*"], order_by="name") for dt in before}
		self.assertEqual(before, after)
