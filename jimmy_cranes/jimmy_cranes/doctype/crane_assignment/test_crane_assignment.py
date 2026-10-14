from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from jimmy_cranes.jimmy_cranes.doctype.crane_timesheet.crane_timesheet import default_timesheet_entries
from jimmy_cranes.rental_operations import crane_action
from jimmy_cranes.rental_queries import (
	assigned_crane_query,
	crane_availability,
	get_project_timeline,
	project_overview,
)
from jimmy_cranes.rental_validation import assignment_progress


class TestCraneRental(FrappeTestCase):
	def setUp(self):
		self.key = frappe.generate_hash(length=8)
		self.base = getdate(today()) - timedelta(days=20)
		self.customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "Rental " + self.key,
				"customer_type": "Company",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
			}
		).insert()
		self.project = self.new_project()
		self.other_project = self.new_project()
		self.cranes = [self.new_crane(i) for i in range(3)]
		self.operators = [
			frappe.get_doc(
				{"doctype": "Crane Operator", "operator_name": f"Operator {self.key} {i}"}
			).insert()
			for i in range(2)
		]

	def d(self, number):
		return str(self.base + timedelta(days=number))

	def new_project(self):
		return frappe.get_doc(
			{
				"doctype": "Project",
				"company": frappe.get_all("Company", pluck="name", limit=1)[0],
				"percent_complete_method": "Manual",
				"status": "Open",
				"project_name": "Project " + frappe.generate_hash(length=8),
				"customer": self.customer.name,
				"expected_start_date": self.d(0),
				"expected_end_date": self.d(70),
			}
		).insert()

	def new_crane(self, index):
		return frappe.get_doc({"doctype": "Crane", "crane_name": f"Crane {self.key} {index}"}).insert()

	def assignment(self, cranes=None, project=None, start=0, end=30):
		return frappe.get_doc(
			{
				"doctype": "Crane Assignment",
				"project": (project or self.project).name,
				"assigned_cranes": [
					{"crane": c.name, "start_date": self.d(start), "expected_end_date": self.d(end)}
					for c in (cranes or self.cranes[:1])
				],
			}
		).insert()

	def action(self, doc, action, rows=None, day=0, reason=None):
		result = crane_action(
			doc.name, doc.project, rows or [r.name for r in doc.assigned_cranes], action, self.d(day), reason
		)
		doc.reload()
		return result

	def active(self, cranes=None, end=30):
		doc = self.assignment(cranes=cranes, end=end)
		self.action(doc, "Reserve")
		return doc

	def sheet(self, entries=None, crane=None, project=None, start=0, end=20):
		return frappe.get_doc(
			{
				"doctype": "Crane Timesheet",
				"project": (project or self.project).name,
				"crane": (crane or self.cranes[0]).name,
				"period_start": self.d(start),
				"period_end": self.d(end),
				"timesheet_entries": entries if entries is not None else [self.shift()],
			}
		)

	def shift(self, day=5, start="08:00:00", end="12:00:00", operator=0, rate=100, overnight=0):
		return {
			"work_date": self.d(day),
			"start_time": start,
			"end_time": end,
			"crane_operator": self.operators[operator].name,
			"price_per_hour": rate,
			"ends_next_day": overnight,
		}

	def test_day_shift_settings_fill_period(self):
		settings = frappe.get_single("Jimmy Cranes Settings")
		settings.day_shift_start_time = "07:30:00"
		settings.day_shift_end_time = "15:30:00"
		settings.save()
		self.assertEqual(settings.day_shift_hours, 8)
		rows = default_timesheet_entries(self.d(1), self.d(3))
		self.assertEqual([row["work_date"] for row in rows], [self.d(1), self.d(2), self.d(3)])
		self.assertTrue(all(row["start_time"] == "07:30:00" for row in rows))
		self.assertTrue(all(row["end_time"] == "15:30:00" for row in rows))
		self.assertTrue(all(row["ends_next_day"] == 0 for row in rows))
		settings.day_shift_end_time = "06:00:00"
		with self.assertRaises(frappe.ValidationError):
			settings.save()

	def test_early_release_inclusive_and_same_project_conflict(self):
		assignment = self.active()
		self.action(assignment, "Release", day=10)
		row = assignment.assigned_cranes[0]
		self.assertEqual(str(row.expected_end_date), self.d(30))
		self.assertEqual(str(row.actual_end_date), self.d(10))
		duplicate = self.assignment(start=10, end=15)
		with self.assertRaises(frappe.ValidationError):
			self.action(duplicate, "Reserve")
		following = self.assignment(project=self.other_project, start=11, end=15)
		self.action(following, "Reserve")
		self.assertEqual(following.assigned_cranes[0].status, "Reserved")

	def test_cancel_work_rejected_and_completion_covers_work(self):
		assignment = self.active()
		self.sheet().insert().submit()
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Cancel", day=8, reason="No participation")
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Release", day=4)
		self.action(assignment, "Release", day=5)
		self.assertEqual(assignment.assigned_cranes[0].status, "Released")

	def test_bulk_failure_is_atomic_and_ids_are_checked(self):
		assignment = self.active(self.cranes)
		names = [r.name for r in assignment.assigned_cranes]
		self.sheet(crane=self.cranes[1], entries=[self.shift(day=8)]).insert()
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Release", names, day=6)
		self.assertTrue(all(r.status == "Reserved" for r in assignment.reload().assigned_cranes))
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Release", ["injected-row"], day=10)
		with self.assertRaises(frappe.ValidationError):
			crane_action(assignment.name, self.other_project.name, names, "Release", self.d(10))

	def test_prices_default_and_preserved(self):
		crane = self.cranes[0]
		self.assertEqual([r.period for r in crane.period_prices], ["Day", "Month", "Year"])
		crane.period_prices[0].price = 150
		crane.save().reload()
		self.assertEqual(crane.period_prices[0].price, 150)
		crane.append("period_prices", {"period": "Day", "price": 10})
		with self.assertRaises(frappe.ValidationError):
			crane.save()
		crane.reload().period_prices[0].price = -1
		with self.assertRaises(frappe.ValidationError):
			crane.save()

	def test_condition_and_future_reservations(self):
		assignment = self.active(end=25)
		future = self.assignment(project=self.other_project, start=30, end=40)
		self.action(future, "Reserve")
		data = crane_availability(self.cranes[0].name, self.d(20))
		self.assertIn("Reserved for selected date", data["indicators"])
		self.assertFalse(data["available"])
		self.assertEqual(len(data["future_reservations"]), 1)
		self.cranes[0].operational_condition = "Maintenance"
		self.cranes[0].save()
		self.assertEqual(assignment.reload().assigned_cranes[0].status, "Reserved")
		next_batch = self.assignment(project=self.other_project, start=41, end=45)
		with self.assertRaises(frappe.ValidationError):
			self.action(next_batch, "Reserve")
		self.assertFalse(crane_availability(self.cranes[0].name, self.d(50))["available"])

	def test_operator_union_and_amount(self):
		self.active()
		sheet = (
			self.sheet([self.shift(), self.shift(start="10:00:00", end="14:00:00", operator=1)])
			.insert()
			.submit()
		)
		self.assertEqual(sheet.total_operator_hours, 8)
		self.assertEqual(sheet.total_crane_billable_hours, 6)
		self.assertEqual(sheet.total_amount, 600)
		self.assertEqual(sum(r.line_amount for r in sheet.timesheet_entries), 800)
		with self.assertRaises(frappe.ValidationError):
			self.sheet().insert()

	def test_ambiguous_rates_invalid_times_and_future(self):
		self.active()
		for entries in (
			[self.shift(), self.shift(start="10:00:00", end="14:00:00", rate=200)],
			[self.shift(start="12:00:00", end="08:00:00")],
			[self.shift(start="12:00:00", end="12:00:00")],
			[self.shift(rate=-1)],
			[self.shift(day=21)],
		):
			with self.assertRaises(frappe.ValidationError):
				self.sheet(entries, end=30).insert()
		with self.assertRaises(frappe.ValidationError):
			self.sheet([]).insert().submit()

	def test_overnight_coverage_and_midnight(self):
		assignment = self.active(end=5)
		with self.assertRaises(frappe.ValidationError):
			self.sheet([self.shift(day=5, start="22:00:00", end="02:00:00", overnight=1)]).insert()
		sheet = self.sheet([self.shift(day=4, start="22:00:00", end="02:00:00", overnight=1)]).insert()
		self.assertEqual(sheet.total_crane_billable_hours, 4)
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Release", day=4)
		midnight = self.sheet(
			[self.shift(day=5, start="22:00:00", end="00:00:00", overnight=1)], end=5
		).insert()
		self.assertEqual(midnight.total_crane_billable_hours, 2)

	def test_submission_immutable_cancel_amend(self):
		self.active()
		sheet = self.sheet().insert().submit()
		sheet.timesheet_entries[0].price_per_hour = 200
		with self.assertRaises(frappe.UpdateAfterSubmitError):
			sheet.save()
		sheet.reload().cancel()
		amendment = frappe.copy_doc(sheet)
		amendment.amended_from = sheet.name
		amendment.docstatus = 0
		amendment.insert().submit()
		self.assertEqual(amendment.docstatus, 1)

	def test_history_cannot_be_removed_or_dates_shortened(self):
		assignment = self.active()
		self.sheet().insert().submit()
		assignment.assigned_cranes[0].expected_end_date = self.d(4)
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		assignment.reload().assigned_cranes = []
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Crane Assignment", assignment.name)

	def test_timeline_layers_and_readonly_overview(self):
		assignment = self.active()
		self.sheet().insert()
		data = get_project_timeline(self.project.name, self.d(0), self.d(30))
		lane = data["cranes"][0]
		self.assertEqual(str(lane["segments"][0]["end_date"]), self.d(30))
		self.assertEqual(lane["work"][0]["operator_hours"], 4)
		self.assertEqual(lane["work"][0]["statuses"], ["Draft"])
		self.assertEqual(project_overview(self.project.name)[0].assignment, assignment.name)
		self.assertEqual(project_overview(self.project.name)[0].crane_name, self.cranes[0].crane_name)

	def test_permission_checks(self):
		assignment = self.assignment()
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				crane_action(
					assignment.name, self.project.name, [assignment.assigned_cranes[0].name], "Reserve"
				)
			with self.assertRaises(frappe.PermissionError):
				project_overview(self.project.name)
		finally:
			frappe.set_user("Administrator")

	def close_project(self, status="Completed"):
		self.project.reload()
		self.project.status = status
		self.project.save()

	def test_future_booking_and_no_automatic_transitions(self):
		assignment = self.assignment(cranes=self.cranes[:2], start=30, end=60)
		self.action(assignment, "Reserve")
		self.assertNotIn("status", assignment.as_dict())
		self.assertEqual(self.project.reload().status, "Open")
		self.assertTrue(all(r.status == "Reserved" for r in assignment.assigned_cranes))
		conflict = self.assignment(cranes=self.cranes[:2], project=self.other_project, start=60, end=65)
		with self.assertRaisesRegex(frappe.ValidationError, self.cranes[0].crane_name):
			self.action(conflict, "Reserve")
		self.assertTrue(all(r.status == "Draft" for r in conflict.reload().assigned_cranes))
		crane_availability(self.cranes[0].name, self.d(30))
		self.assertEqual(assignment.reload().assigned_cranes[0].status, "Reserved")
		self.assertFalse(
			any(
				"jimmy_cranes" in method
				for methods in frappe.get_hooks("scheduler_events").values()
				for method in methods
				if isinstance(method, str)
			)
		)

	def test_work_is_valid_while_reserved(self):
		assignment = self.active()
		self.sheet().insert().submit()
		self.assertEqual(assignment.reload().assigned_cranes[0].status, "Reserved")
		self.assertEqual(self.project.reload().status, "Open")
		self.assertTrue(crane_availability(self.cranes[0].name, self.d(5))["work_recorded"])

	def test_partial_release_and_progress(self):
		cranes = self.cranes + [self.new_crane(i) for i in range(3, 10)]
		assignment = self.active(cranes)
		self.action(assignment, "Release", [r.name for r in assignment.assigned_cranes[:2]], day=14)
		self.assertEqual(assignment.released_cranes, 2)
		self.assertEqual(assignment.reserved_cranes, 8)
		self.assertEqual(assignment.completion_percentage, 20)
		self.assertTrue(all(str(r.expected_end_date) == self.d(30) for r in assignment.assigned_cranes))
		self.assertEqual(str(assignment.assigned_cranes[0].actual_end_date), self.d(14))
		self.assertEqual(self.project.reload().status, "Open")
		following = self.assignment(start=15, end=20, project=self.other_project)
		self.action(following, "Reserve")
		conflicting = self.assignment(start=14, end=14, project=self.other_project)
		with self.assertRaises(frappe.ValidationError):
			self.action(conflicting, "Reserve")

	def test_progress_cancelled_and_draft_denominators(self):
		cranes = self.cranes + [self.new_crane(i) for i in range(3, 10)]
		assignment = self.active(cranes)
		self.action(assignment, "Release", [r.name for r in assignment.assigned_cranes[:3]], day=10)
		self.action(
			assignment,
			"Cancel",
			[r.name for r in assignment.assigned_cranes[8:]],
			day=10,
			reason="Not needed",
		)
		self.assertEqual(assignment.completion_percentage, 37.5)
		self.assertEqual(assignment.total_cranes, 8)
		self.assertEqual(assignment.cancelled_cranes, 2)
		from jimmy_cranes.rental_queries import assignment_summary

		self.assertEqual(assignment_summary(assignment.name)["completion_percentage"], 37.5)
		for states, total, released, percent in [
			([], 0, 0, 0),
			(["Cancelled"], 0, 0, 0),
			(["Released", "Draft", "Cancelled"], 2, 1, 50),
		]:
			data = assignment_progress([frappe._dict(status=s) for s in states])
			self.assertEqual(
				(data["total_cranes"], data["released_cranes"], data["completion_percentage"]),
				(total, released, percent),
			)

	def test_historical_project_and_closing_approval(self):
		assignment = self.active()
		self.action(assignment, "Release", day=8)
		self.assertEqual(self.project.reload().status, "Open")
		sheet = self.sheet().insert()
		with self.assertRaisesRegex(frappe.ValidationError, "draft Crane Timesheets"):
			self.close_project()
		sheet.submit()
		self.close_project()
		self.assertEqual(self.project.status, "Completed")
		with self.assertRaises(frappe.ValidationError):
			self.sheet([self.shift(day=6)]).insert()
		with self.assertRaises(frappe.ValidationError):
			self.assignment(cranes=[self.cranes[2]])
		picked = assigned_crane_query(
			"Crane", "", "name", 0, 20, {"project": self.project.name, "work_date": self.d(5)}
		)
		self.assertEqual(picked[0][0], self.cranes[0].name)
		self.assertEqual(
			assigned_crane_query(
				"Crane", "", "name", 0, 20, {"project": self.project.name, "work_date": self.d(9)}
			),
			[],
		)

	def test_closed_project_authorized_amendment(self):
		assignment = self.active()
		sheet = self.sheet().insert().submit()
		self.action(assignment, "Release", day=8)
		self.close_project()
		sheet.cancel()
		amendment = frappe.copy_doc(sheet)
		amendment.docstatus = 0
		amendment.amended_from = sheet.name
		amendment.timesheet_entries[0].price_per_hour = 120
		amendment.insert().submit()
		self.assertEqual(amendment.total_amount, 480)
		self.assertEqual(self.project.reload().status, "Completed")
		amendment.cancel()
		invalid = frappe.copy_doc(amendment)
		invalid.docstatus = 0
		invalid.amended_from = amendment.name
		invalid.timesheet_entries[0].work_date = self.d(6)
		with self.assertRaisesRegex(frappe.ValidationError, "new work dates"):
			invalid.insert()

	def test_project_close_requires_resolved_rows(self):
		assignment = self.assignment(self.cranes)
		for status in ("Completed", "Cancelled"):
			with self.assertRaisesRegex(frappe.ValidationError, self.cranes[0].crane_name):
				self.close_project(status)
		self.action(assignment, "Reserve")
		with self.assertRaisesRegex(frappe.ValidationError, "Reserved"):
			self.close_project()
		self.action(assignment, "Cancel", day=10, reason="Project called off")
		self.assertEqual(self.project.reload().status, "Open")
		self.close_project("Cancelled")
		with self.assertRaises(frappe.ValidationError):
			self.sheet().insert()

	def test_overdue_reservation_requires_release_confirmation(self):
		assignment = self.active(end=5)
		data = crane_availability(self.cranes[0].name, self.d(20))
		self.assertFalse(data["available"])
		self.assertTrue(data["overdue"])
		future = self.assignment(project=self.other_project, start=21, end=25)
		with self.assertRaisesRegex(frappe.ValidationError, "overdue"):
			self.action(future, "Reserve")
		self.action(assignment, "Release", day=8)
		self.action(future, "Reserve")
		self.assertTrue(crane_availability(self.cranes[0].name, self.d(9))["available"])
		self.assertFalse(crane_availability(self.cranes[0].name, self.d(8))["available"])

	def test_late_release_conflict_and_no_work_after_release(self):
		assignment = self.active(end=5)
		self.action(assignment, "Release", day=8)
		self.assertEqual(str(assignment.assigned_cranes[0].expected_end_date), self.d(5))
		self.sheet([self.shift(day=8)]).insert()
		with self.assertRaises(frappe.ValidationError):
			self.sheet([self.shift(day=9)]).insert()
		other = self.assignment(project=self.other_project, start=9, end=15)
		self.action(other, "Reserve")
		with self.assertRaises(frappe.ValidationError):
			assignment.assigned_cranes[0].actual_end_date = self.d(10)
			assignment.save()

	def test_cancel_draft_work_rejected(self):
		assignment = self.active()
		self.sheet().insert()
		with self.assertRaisesRegex(frappe.ValidationError, "Use Release"):
			self.action(assignment, "Cancel", day=10, reason="Not needed")
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Release", day=4)

	def test_manual_status_injection_is_rejected(self):
		assignment = self.assignment()
		assignment.assigned_cranes[0].status = "Reserved"
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		assignment.reload().assigned_cranes[0].status = "In Progress"
		with self.assertRaises(frappe.ValidationError):
			assignment.save()

	def test_100_crane_batch(self):
		cranes = self.cranes + [self.new_crane(i) for i in range(3, 105)]
		assignment = self.active(cranes)
		self.action(assignment, "Release", [r.name for r in assignment.assigned_cranes[:2]], day=10)
		self.assertEqual(assignment.reserved_cranes, 103)
		self.assertEqual(len(get_project_timeline(self.project.name, self.d(0), self.d(30))["cranes"]), 105)
		self.action(assignment, "Release", [r.name for r in assignment.assigned_cranes[2:]], day=10)
		self.assertEqual(assignment.completion_percentage, 100)
		self.assertEqual(self.project.reload().status, "Open")

	def test_native_task_completion_does_not_close_rental_project(self):
		self.project.percent_complete_method = "Task Completion"
		self.project.save()
		self.active()
		self.assertEqual(self.project.reload().percent_complete_method, "Manual")
		task = frappe.get_doc(
			{"doctype": "Task", "subject": "Rental task " + self.key, "project": self.project.name}
		).insert()
		task.status = "Completed"
		task.save()
		self.assertEqual(self.project.reload().status, "Open")

	def test_late_release_checks_other_bookings(self):
		assignment = self.active(end=5)
		following = self.assignment(project=self.other_project, start=6, end=15)
		self.action(following, "Reserve")
		with self.assertRaisesRegex(frappe.ValidationError, self.cranes[0].crane_name):
			self.action(assignment, "Release", day=8)
		self.assertEqual(assignment.reload().assigned_cranes[0].status, "Reserved")
		self.assertFalse(assignment.assigned_cranes[0].actual_end_date)

	def test_cancelled_batch_and_dates_on_load(self):
		assignment = self.assignment(self.cranes)
		self.action(assignment, "Cancel", day=10, reason="Not needed")
		self.assertEqual(assignment.total_cranes, 0)
		self.assertEqual(assignment.completion_percentage, 0)
		self.assertEqual(assignment.cancelled_cranes, 3)
		self.project.expected_end_date = self.d(71)
		self.project.save()
		assignment.reload().onload()
		self.assertEqual(str(assignment.project_end_date), self.d(71))
		self.assertEqual(assignment.completion_percentage, 0)

	def test_date_range_availability(self):
		assignment = self.active()
		self.action(assignment, "Release", day=10)
		self.assertFalse(crane_availability(self.cranes[0].name, self.d(9), self.d(12))["available"])
		self.assertTrue(crane_availability(self.cranes[0].name, self.d(11), self.d(12))["available"])

	def test_unrelated_native_project_keeps_task_completion_behavior(self):
		self.other_project.percent_complete_method = "Task Completion"
		self.other_project.save()
		task = frappe.get_doc(
			{
				"doctype": "Task",
				"subject": "Native task " + self.key,
				"project": self.other_project.name,
			}
		).insert()
		task.status = "Completed"
		task.save()
		self.assertEqual(self.other_project.reload().status, "Completed")
