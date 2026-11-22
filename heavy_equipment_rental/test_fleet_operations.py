from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from heavy_equipment_rental.fleet_operations import DAY
from heavy_equipment_rental.heavy_equipment_rental.report.fleet_utilization_and_availability import (
	fleet_utilization_and_availability as utilization,
)
from heavy_equipment_rental.heavy_equipment_rental.report.maintenance_and_downtime import (
	maintenance_and_downtime as maintenance,
)


class TestFleetOperations(FrappeTestCase):
	def setUp(self):
		self.today = getdate()
		self.crane = frappe.get_doc(
			dict(doctype="Crane", crane_id=frappe.generate_hash(length=12), crane_name="Dispatch report test")
		).insert()
		self.filters = dict(crane=self.crane.name, from_date=self.today - 5 * DAY, to_date=self.today)
		self.contract = frappe.get_doc(
			dict(
				doctype="Rental Contract",
				customer=frappe.db.get_value("Customer", {}, "name"),
				location=frappe.db.get_value("Location", {}, "name"),
				assigned_cranes=[
					dict(
						crane=self.crane.name,
						rental_rate_unit="Hour",
						rental_rate=100,
						start_date=self.today - 5 * DAY,
						expected_end_date=self.today + DAY,
					),
					dict(
						crane=self.crane.name,
						rental_rate_unit="Day",
						rental_rate=500,
						start_date=self.today + 4 * DAY,
						expected_end_date=self.today + 5 * DAY,
					),
				],
			)
		).insert()

	def test_submitted_work_calendar_days_and_free_window(self):
		first = self.today - 5 * DAY
		sheet = frappe.get_doc(
			dict(
				doctype="Crane Timesheet",
				crane=self.crane.name,
				assignment=self.contract.name,
				location=self.contract.location,
				customer=self.contract.customer,
				period_start=first,
				period_end=first + 3 * DAY,
				driver=frappe.db.get_value("Employee", {}, "name"),
				timesheet_entries=[
					dict(
						work_date=first, start_time="23:00", end_time="01:00", ends_next_day=1, worked_hours=2
					),
					dict(
						work_date=first + DAY,
						start_time="04:00",
						end_time="05:00",
						worked_hours=0,
						overtime_hours=1,
					),
					dict(work_date=first + 2 * DAY, worked_hours=0),
				],
			)
		).insert()
		row = utilization.execute(self.filters)[1][0]
		self.assertEqual((row["missing_days"], row["worked_days"]), (5, 0))
		sheet.submit()
		result = utilization.execute(self.filters)
		self.assertEqual(result[3]["data"]["datasets"][0]["values"], [2, 1, 2])
		self.assertEqual(result[1][-1]["utilization"], result[4][0]["value"])
		self.assertEqual(len(utilization.day_details(**self.filters, metric="missing_days")), 2)
		row = result[1][0]
		self.assertEqual(
			(
				row["booked_days"],
				row["elapsed_days"],
				row["worked_days"],
				row["downtime_days"],
				row["missing_days"],
				row["utilization"],
			),
			(6, 5, 2, 1, 2, 40),
		)
		self.assertEqual(
			(row["free_from"], row["free_through"]), (self.today + 2 * DAY, self.today + 3 * DAY)
		)
		clipped = utilization.execute(dict(self.filters, from_date=first + DAY, to_date=first + DAY))[1][0]
		self.assertEqual((clipped["worked_days"], clipped["utilization"]), (1, 100))
		sheet.cancel()
		self.assertEqual(utilization.execute(self.filters)[1][0]["worked_days"], 0)

	def test_overlapping_repairs_and_repeated_booking_risk(self):
		jobs = []
		for age in (3, 1):
			jobs.append(
				frappe.get_doc(
					dict(
						doctype="Crane Maintenance",
						crane=self.crane.name,
						company=self.contract.company,
						status="In Progress",
						cost_treatment="No Cost",
						actual_start_date=self.today - age * DAY,
						actual_end_date=self.today - age * DAY,
						description="Availability test",
					)
				).insert()
			)
		row = utilization.execute(self.filters)[1][0]
		self.assertEqual(row["maintenance_days"], 4)
		self.assertIsNone(row["free_from"])
		history = maintenance.execute(self.filters)[1]
		self.assertEqual(
			sorted((r["repair_days"], r["risk_count"], r["cost"]) for r in history if not r.get("is_total")),
			[(2, 2, 0), (4, 2, 0)],
		)
		result = maintenance.execute(dict(self.filters, view="Bookings at Risk"))
		self.assertEqual(len(result[1]), 4)
		self.assertEqual(result[4][1]["value"], 2)
		self.assertTrue(all(r["contract"] == self.contract.name for r in result[1]))
		for job in jobs:
			job.submit()
		self.assertEqual(len(maintenance.execute(dict(self.filters, view="Bookings at Risk"))[1]), 0)
		self.assertEqual(utilization.execute(self.filters)[1][0]["maintenance_days"], 2)
		jobs[0].cancel()
		self.assertEqual(len(maintenance.execute(self.filters)[1]), 2)

	def test_incomplete_booking_visibility_and_future_only_period(self):
		with patch("heavy_equipment_rental.fleet_operations.visible_allocations", return_value=[]):
			row = utilization.execute(self.filters)[1][0]
			self.assertIsNone(row["free_from"])
			self.assertIsNone(row["utilization"])
		future = dict(self.filters, from_date=self.today + DAY, to_date=self.today + 6 * DAY)
		row = utilization.execute(future)[1][0]
		self.assertEqual((row["booked_days"], row["elapsed_days"], row["missing_days"]), (3, 0, 0))
		self.assertIsNone(row["utilization"])

	def test_report_permissions(self):
		frappe.set_user("Guest")
		try:
			for report in (utilization, maintenance):
				with self.assertRaises(frappe.PermissionError):
					report.execute(self.filters)
		finally:
			frappe.set_user("Administrator")
