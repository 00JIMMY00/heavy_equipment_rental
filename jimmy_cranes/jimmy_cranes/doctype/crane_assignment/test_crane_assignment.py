from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from jimmy_cranes.rental_operations import crane_action, project_action, start_scheduled_projects
from jimmy_cranes.rental_queries import (
	assigned_crane_query,
	crane_availability,
	get_project_timeline,
	project_overview,
)
from jimmy_cranes.rental_validation import derived_status


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
				"doctype": "Crane Project",
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
		project_action(self.project.name, "Start")
		doc = self.assignment(cranes=cranes, end=end)
		self.action(doc, "Start")
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

	def test_independent_project_and_row_lifecycles(self):
		assignment = self.assignment(self.cranes)
		project_action(self.project.name, "Reserve")
		self.assertEqual(assignment.reload().status, "Draft")
		self.action(assignment, "Reserve")
		project_action(self.project.name, "Start")
		self.assertEqual(assignment.reload().status, "Reserved")
		self.action(assignment, "Start", [assignment.assigned_cranes[0].name])
		self.action(assignment, "Complete", [assignment.assigned_cranes[0].name], day=10)
		self.assertEqual(assignment.status, "In Progress")
		self.assertEqual(assignment.assigned_cranes[1].status, "Reserved")
		with self.assertRaises(frappe.ValidationError):
			project_action(self.project.name, "Complete", self.d(10))
		self.action(
			assignment,
			"Cancel",
			[r.name for r in assignment.assigned_cranes[1:]],
			day=10,
			reason="Not needed",
		)
		self.assertEqual(assignment.status, "Complete")
		self.assertEqual(self.project.reload().status, "In Progress")
		project_action(self.project.name, "Complete", self.d(10))
		self.assertEqual(self.project.reload().status, "Complete")
		with self.assertRaises(frappe.ValidationError):
			self.assignment(cranes=[self.cranes[2]], start=12)
		with self.assertRaises(frappe.ValidationError):
			project_action(self.project.name, "Start")

	def test_early_release_inclusive_and_same_project_conflict(self):
		assignment = self.active()
		self.action(assignment, "Complete", day=10)
		row = assignment.assigned_cranes[0]
		self.assertEqual(str(row.expected_end_date), self.d(30))
		self.assertEqual(str(row.actual_end_date), self.d(10))
		duplicate = self.assignment(start=10, end=15)
		with self.assertRaises(frappe.ValidationError):
			self.action(duplicate, "Reserve")
		following = self.assignment(project=self.other_project, start=11, end=15)
		self.action(following, "Reserve")
		self.assertEqual(following.status, "Reserved")

	def test_cancel_work_rejected_and_completion_covers_work(self):
		assignment = self.active()
		self.sheet().insert().submit()
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Cancel", day=8, reason="No participation")
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Complete", day=4)
		self.action(assignment, "Complete", day=5)
		self.assertEqual(assignment.status, "Complete")

	def test_bulk_failure_is_atomic_and_ids_are_checked(self):
		assignment = self.active(self.cranes)
		names = [r.name for r in assignment.assigned_cranes]
		self.sheet(crane=self.cranes[1], entries=[self.shift(day=8)]).insert()
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Complete", names, day=6)
		self.assertTrue(all(r.status == "In Progress" for r in assignment.reload().assigned_cranes))
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Complete", ["injected-row"], day=10)
		with self.assertRaises(frappe.ValidationError):
			crane_action(assignment.name, self.other_project.name, names, "Complete", self.d(10))

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
		self.assertEqual(data["activity"], "Working")
		self.assertFalse(data["available"])
		self.assertEqual(len(data["future_reservations"]), 1)
		self.cranes[0].operational_condition = "Maintenance"
		self.cranes[0].save()
		self.assertEqual(assignment.reload().status, "In Progress")
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
			self.action(assignment, "Complete", day=4)
		midnight = self.sheet(
			[self.shift(day=5, start="22:00:00", end="00:00:00", overnight=1)], end=5
		).insert()
		self.assertEqual(midnight.total_crane_billable_hours, 2)

	def test_historical_complete_project_and_picker(self):
		assignment = self.active()
		self.action(assignment, "Complete", day=8)
		project_action(self.project.name, "Complete", self.d(10))
		self.sheet().insert().submit()
		with self.assertRaises(frappe.ValidationError):
			self.sheet([self.shift(day=11)]).insert()
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
		with self.assertRaises(frappe.ValidationError):
			self.sheet(crane=self.cranes[2]).insert()

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

	def test_manual_status_injection_and_legacy_spoof(self):
		assignment = self.assignment()
		assignment.assigned_cranes[0].status = "Reserved"
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		self.project.status = "In Progress"
		with self.assertRaises(frappe.ValidationError):
			self.project.save()
		sheet = self.sheet()
		sheet.legacy_needs_review = 1
		with self.assertRaises(frappe.ValidationError):
			sheet.insert()

	def test_timeline_layers_and_readonly_overview(self):
		assignment = self.active()
		self.sheet().insert()
		data = get_project_timeline(self.project.name, self.d(0), self.d(30))
		lane = data["cranes"][0]
		self.assertEqual(str(lane["segments"][0]["end_date"]), self.d(30))
		self.assertEqual(str(lane["segments"][0]["actual_start_date"]), self.d(0))
		self.assertEqual(lane["work"][0]["operator_hours"], 4)
		self.assertEqual(lane["work"][0]["statuses"], ["Draft"])
		self.assertEqual(project_overview(self.project.name)[0].assignment, assignment.name)

	def test_permission_checks(self):
		assignment = self.assignment()
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				project_action(self.project.name, "Start")
			with self.assertRaises(frappe.PermissionError):
				crane_action(
					assignment.name, self.project.name, [assignment.assigned_cranes[0].name], "Reserve"
				)
			with self.assertRaises(frappe.PermissionError):
				project_overview(self.project.name)
		finally:
			frappe.set_user("Administrator")

	def test_100_crane_batch_and_partial_completion(self):
		cranes = self.cranes + [self.new_crane(i) for i in range(3, 100)]
		assignment = self.active(cranes)
		self.action(assignment, "Complete", [r.name for r in assignment.assigned_cranes[:2]], day=10)
		self.assertEqual(assignment.status, "In Progress")
		self.assertEqual(sum(r.status == "In Progress" for r in assignment.assigned_cranes), 98)
		self.assertEqual(len(get_project_timeline(self.project.name, self.d(0), self.d(30))["cranes"]), 100)
		self.action(assignment, "Complete", [r.name for r in assignment.assigned_cranes[2:]], day=10)
		self.assertEqual(assignment.status, "Complete")

	def test_derived_status_terminal_edges(self):
		for states, expected in [
			([], "Draft"),
			(["Draft", "Cancelled"], "Draft"),
			(["Reserved", "Cancelled"], "Reserved"),
			(["Complete", "Draft"], "In Progress"),
			(["Complete", "Cancelled"], "Complete"),
			(["Cancelled"], "Cancelled"),
		]:
			self.assertEqual(derived_status([frappe._dict(status=s) for s in states]), expected)

	def test_automatic_start_requires_opt_in(self):
		self.project.auto_start_on_date = 1
		self.project.save()
		start_scheduled_projects()
		self.assertEqual(self.project.reload().status, "In Progress")
		self.assertEqual(self.other_project.reload().status, "Draft")

	def test_late_completion_requires_reason_and_no_overlap(self):
		assignment = self.active(end=5)
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Complete", day=8)
		self.action(assignment, "Complete", day=8, reason="Extended work agreed")
		self.assertEqual(str(assignment.assigned_cranes[0].expected_end_date), self.d(5))

	def test_legacy_shift_review_and_amendment(self):
		self.active()
		sheet = self.sheet().insert()
		original = frappe.as_json(sheet.as_dict())
		frappe.db.set_value(
			"Crane Timesheet",
			sheet.name,
			{"legacy_snapshot": original, "legacy_source_status": "Approved", "legacy_needs_review": 1},
		)
		frappe.db.set_value(
			"Timesheet Entry", sheet.timesheet_entries[0].name, {"start_time": None, "end_time": None}
		)
		sheet.reload()
		with self.assertRaises(frappe.ValidationError):
			sheet.submit()
		sheet.reload()
		sheet.timesheet_entries[0].start_time = "08:00:00"
		sheet.timesheet_entries[0].end_time = "12:00:00"
		sheet.save()
		self.assertEqual(sheet.legacy_needs_review, 0)
		self.assertEqual(sheet.legacy_snapshot, original)
		sheet.submit().cancel()
		amendment = frappe.copy_doc(sheet)
		amendment.docstatus = 0
		amendment.amended_from = sheet.name
		amendment.insert().submit()
		self.assertEqual(amendment.docstatus, 1)
		self.assertFalse(amendment.legacy_snapshot)

	def test_migration_does_not_reset_new_crane_condition(self):
		from jimmy_cranes.migration import migrate_existing

		crane = self.cranes[0]
		crane.operational_condition = "Maintenance"
		crane.save()
		migrate_existing()
		self.assertEqual(crane.reload().operational_condition, "Maintenance")
