from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from jimmy_cranes.jimmy_cranes.doctype.crane_timesheet.crane_timesheet import default_timesheet_entries
from jimmy_cranes.rental_operations import crane_action, project_action
from jimmy_cranes.rental_queries import (
	assigned_crane_query,
	crane_availability,
	get_project_timeline,
	project_overview,
)


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
				{
					"doctype": "Crane Driver",
					"operator_name": f"Driver {self.key} {i}",
					"company": frappe.db.get_value("Company", {}, "name"),
					"gender": frappe.db.get_value("Gender", {}, "name"),
					"date_of_birth": "1990-01-01",
					"date_of_joining": "2020-01-01",
				}
			).insert()
			for i in range(2)
		]

	def d(self, number):
		return str(self.base + timedelta(days=number))

	def test_driver_employee_and_project_expense(self):
		self.assignment()
		driver = self.operators[0]
		self.assertTrue(driver.employee)
		self.assertEqual(frappe.db.get_value("Employee", driver.employee, "employee_name"), driver.operator_name)
		expense_type = frappe.get_doc({
			"doctype": "Expense Type", "expense_type_name": "Fuel " + self.key
		}).insert()
		expense = frappe.get_doc({
			"doctype": "Expense Entry",
			"project": self.project.name,
			"posting_date": self.d(5),
			"expense_type": expense_type.name,
			"amount": 125,
			"crane": self.cranes[0].name,
			"employee": driver.employee,
		}).insert()
		self.assertEqual(expense.project, self.project.name)
		self.assertEqual(expense.employee, driver.employee)
		self.assertEqual(frappe.db.count("Expense Entry", {"project": self.project.name}), 1)
		expense.project = self.other_project.name
		with self.assertRaisesRegex(frappe.ValidationError, "assigned to this Crane Project"):
			expense.save()
		expense.project = self.project.name
		expense.submit()
		self.assertEqual(expense.docstatus, 1)
		expense.cancel()
		self.assertEqual(expense.docstatus, 2)

	def new_project(self):
		return frappe.get_doc(
			{
				"doctype": "Crane Project",
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

	def test_booking_end_is_inclusive_and_following_day_is_free(self):
		self.active(end=10)
		duplicate = self.assignment(start=10, end=15)
		with self.assertRaises(frappe.ValidationError):
			self.action(duplicate, "Reserve")
		following = self.assignment(project=self.other_project, start=11, end=15)
		self.action(following, "Reserve")
		self.assertEqual(following.assigned_cranes[0].status, "Reserved")

	def test_cancel_work_rejected_and_booking_covers_work(self):
		assignment = self.active()
		self.sheet().insert().submit()
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Cancel", day=8, reason="No participation")
		assignment.assigned_cranes[0].expected_end_date = self.d(4)
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		self.assertEqual(assignment.reload().assigned_cranes[0].status, "Reserved")

	def test_bulk_failure_is_atomic_and_ids_are_checked(self):
		assignment = self.active(self.cranes)
		names = [r.name for r in assignment.assigned_cranes]
		self.sheet(crane=self.cranes[1], entries=[self.shift(day=8)]).insert()
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Cancel", names, day=6, reason="Not needed")
		self.assertTrue(all(r.status == "Reserved" for r in assignment.reload().assigned_cranes))
		with self.assertRaises(frappe.ValidationError):
			self.action(assignment, "Cancel", ["injected-row"], day=10, reason="Not needed")
		with self.assertRaises(frappe.ValidationError):
			crane_action(assignment.name, self.other_project.name, names, "Cancel", self.d(10), "Not needed")

	def test_prices_default_and_preserved(self):
		crane = self.cranes[0]
		self.assertEqual([r.period for r in crane.period_prices], ["Hour", "Day", "Month", "Year"])
		crane.period_prices[0].price = 150
		crane.save().reload()
		self.assertEqual(crane.period_prices[0].price, 150)
		crane.append("period_prices", {"period": "Day", "price": 10})
		with self.assertRaises(frappe.ValidationError):
			crane.save()
		crane.reload().period_prices[0].price = -1
		with self.assertRaises(frappe.ValidationError):
			crane.save()

	def test_assignment_dates_remain_within_project_dates(self):
		for start, end in ((-1, 5), (5, 71)):
			with self.assertRaisesRegex(frappe.ValidationError, "within the Project dates"):
				self.assignment(start=start, end=end)
		assignment = self.assignment(start=5, end=30)
		assignment.assigned_cranes[0].start_date = self.d(-1)
		with self.assertRaisesRegex(frappe.ValidationError, "within the Project dates"):
			assignment.save()
		assignment.reload()
		self.project.expected_end_date = self.d(29)
		with self.assertRaisesRegex(frappe.ValidationError, "must cover assignment"):
			self.project.save()
		self.project.reload()
		self.project.expected_start_date = self.d(6)
		with self.assertRaisesRegex(frappe.ValidationError, "must cover assignment"):
			self.project.save()

	def test_timesheet_hourly_price_priority(self):
		crane = self.cranes[0]
		next(row for row in crane.period_prices if row.period == "Hour").price = 40
		crane.save()
		assignment = self.assignment()
		self.action(assignment, "Reserve")
		explicit = self.sheet(entries=[self.shift(day=5, rate=120)]).insert()
		self.assertEqual(explicit.timesheet_entries[0].price_per_hour, 120)
		self.assertEqual(explicit.total_amount, 480)
		fallback = self.sheet(entries=[self.shift(day=6, rate=0)]).insert()
		self.assertEqual(fallback.timesheet_entries[0].price_per_hour, 40)
		self.assertEqual(fallback.total_amount, 160)
		assignment.assigned_cranes[0].rental_rate = 80
		assignment.save()
		from_assignment = self.sheet(entries=[self.shift(day=7, rate=0)]).insert()
		self.assertEqual(from_assignment.timesheet_entries[0].price_per_hour, 80)
		self.assertEqual(from_assignment.total_amount, 320)
		assignment.assigned_cranes[0].rental_rate_unit = "Day"
		assignment.save()
		from_crane = self.sheet(entries=[self.shift(day=8, rate=0)]).insert()
		self.assertEqual(from_crane.timesheet_entries[0].price_per_hour, 40)

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
		marker = get_project_timeline(self.project.name, self.d(5), self.d(5))["cranes"][0]["work"][0]
		self.assertEqual(marker["crane_hours"], 6)
		self.assertEqual(marker["operator_hours"], 8)
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
		assignment.assigned_cranes[0].expected_end_date = self.d(4)
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
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
		other_assignment = self.assignment(cranes=[self.cranes[1]])
		self.sheet().insert()
		data = get_project_timeline(self.project.name, self.d(0), self.d(30), assignment=assignment.name)
		self.assertEqual(len(data["cranes"]), 1)
		self.assertNotEqual(data["cranes"][0]["crane"], other_assignment.assigned_cranes[0].crane)
		with self.assertRaises(frappe.ValidationError):
			get_project_timeline(self.other_project.name, self.d(0), self.d(30), assignment=assignment.name)
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
		project_action(self.project.name, {"Completed": "Complete", "Cancelled": "Cancel"}[status], reason="Test closure")
		self.project.reload()

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

	def test_historical_project_and_closing_approval(self):
		assignment = self.active()
		assignment.assigned_cranes[0].expected_end_date = self.d(8)
		assignment.save()
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
		self.close_project()
		self.assertEqual(self.project.status, "Completed")
		with self.assertRaises(frappe.ValidationError):
			self.sheet().insert()

	def test_cancel_draft_work_rejected(self):
		assignment = self.active()
		self.sheet().insert()
		with self.assertRaisesRegex(frappe.ValidationError, "recorded work"):
			self.action(assignment, "Cancel", day=10, reason="Not needed")
		with self.assertRaisesRegex(frappe.ValidationError, "Unknown crane action"):
			self.action(assignment, "Release", day=4)

	def test_manual_status_injection_is_rejected(self):
		assignment = self.assignment()
		assignment.assigned_cranes[0].status = "Reserved"
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		assignment.reload().assigned_cranes[0].status = "In Progress"
		with self.assertRaises(frappe.ValidationError):
			assignment.save()
		assignment.reload().assigned_cranes[0].status = "Released"
		with self.assertRaises(frappe.ValidationError):
			assignment.save()

	def test_100_crane_batch(self):
		cranes = self.cranes + [self.new_crane(i) for i in range(3, 105)]
		assignment = self.active(cranes)
		self.assertEqual(len(get_project_timeline(self.project.name, self.d(0), self.d(30))["cranes"]), 105)
		self.action(assignment, "Cancel", [r.name for r in assignment.assigned_cranes[:2]], day=10, reason="Not needed")
		self.assertEqual(sum(r.status == "Reserved" for r in assignment.assigned_cranes), 103)
		self.assertEqual(self.project.reload().status, "Open")

	def test_cancelled_batch_and_dates_on_load(self):
		assignment = self.assignment(self.cranes)
		self.action(assignment, "Cancel", day=10, reason="Not needed")
		self.assertTrue(all(row.status == "Cancelled" for row in assignment.assigned_cranes))
		self.project.expected_end_date = self.d(71)
		self.project.save()
		assignment.reload().onload()
		self.assertEqual(str(assignment.project_end_date), self.d(71))

	def test_date_range_availability(self):
		self.active(end=10)
		self.assertFalse(crane_availability(self.cranes[0].name, self.d(9), self.d(12))["available"])
		self.assertTrue(crane_availability(self.cranes[0].name, self.d(11), self.d(12))["available"])


	def test_crane_item_and_sales_invoices_use_contract_rates(self):
		from calendar import monthrange

		from jimmy_cranes.billing import generate_sales_invoice

		crane = self.cranes[0].reload()
		item = frappe.get_doc("Item", crane.item)
		self.assertEqual(item.item_name, crane.crane_name)
		self.assertEqual(item.stock_uom, "Hour")
		self.assertEqual(item.is_stock_item, 0)
		self.assertEqual(item.is_sales_item, 1)

		assignment = self.assignment()
		assignment.assigned_cranes[0].rental_rate = 100
		assignment.assigned_cranes[0].rental_rate_unit = "Day"
		assignment.save()
		self.action(assignment, "Reserve")
		first = self.sheet(entries=[self.shift(day=5)])
		first.insert().submit()
		result = generate_sales_invoice(timesheet=first.name)
		invoice = frappe.get_doc("Sales Invoice", result["name"])
		self.assertEqual(invoice.docstatus, 0)
		self.assertEqual(invoice.customer, self.customer.name)
		self.assertEqual(invoice.items[0].item_code, crane.item)
		self.assertAlmostEqual(invoice.grand_total, 100)
		self.assertEqual(generate_sales_invoice(timesheet=first.name)["name"], invoice.name)

		assignment.reload().assigned_cranes[0].rental_rate = 3100
		assignment.assigned_cranes[0].rental_rate_unit = "Month"
		assignment.save()
		second = self.sheet(entries=[self.shift(day=6)])
		second.insert().submit()
		result = generate_sales_invoice(project=self.project.name)
		monthly_invoice = frappe.get_doc("Sales Invoice", result["name"])
		month_day = getdate(self.d(6))
		self.assertEqual(result["timesheets"], [second.name])
		self.assertAlmostEqual(monthly_invoice.grand_total, 3100 / monthrange(month_day.year, month_day.month)[1], places=2)
		existing = generate_sales_invoice(project=self.project.name)
		self.assertEqual({row["name"] for row in existing["existing_invoices"]}, {invoice.name, monthly_invoice.name})

	def test_project_invoice_summary_and_explicit_draft_rebuild(self):
		from jimmy_cranes.billing import generate_sales_invoice, project_invoice_summary, rebuild_draft_invoice

		assignment = self.assignment()
		assignment.assigned_cranes[0].rental_rate = 80
		assignment.save()
		self.action(assignment, "Reserve")
		sheet = self.sheet(entries=[self.shift(day=5)])
		sheet.insert().submit()
		invoice_name = generate_sales_invoice(project=self.project.name)["name"]
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		invoice.items[0].item_code = self.cranes[1].item
		invoice.items[0].item_name = self.cranes[1].crane_name
		invoice.items[0].rate = 0
		invoice.save()
		summary = project_invoice_summary(self.project.name)
		self.assertEqual(summary["invoices"][0]["name"], invoice_name)
		self.assertEqual(summary["invoices"][0]["timesheets"], [sheet.name])
		self.assertTrue(summary["invoices"][0]["zero_total"])
		self.assertEqual(summary["invoices"][0]["missing_cranes"], [self.cranes[0].crane_name])
		self.assertEqual(generate_sales_invoice(project=self.project.name)["existing_invoices"][0]["name"], invoice_name)
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			rebuild_draft_invoice(self.project.name, invoice_name, "")
		rebuild_draft_invoice(self.project.name, invoice_name, "Restore agreed crane rate")
		self.assertEqual(frappe.get_doc("Sales Invoice", invoice_name).grand_total, 400)
		self.assertFalse(project_invoice_summary(self.project.name)["invoices"][0]["zero_total"])

	def test_hourly_invoice_and_timesheet_cancellation_guard(self):
		from jimmy_cranes.billing import generate_sales_invoice

		assignment = self.assignment()
		assignment.assigned_cranes[0].rental_rate = 75
		assignment.save()
		self.action(assignment, "Reserve")
		sheet = self.sheet(entries=[self.shift(day=5, start="08:00:00", end="12:00:00")])
		sheet.insert().submit()
		invoice_name = generate_sales_invoice(timesheet=sheet.name)["name"]
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		self.assertEqual(invoice.items[0].qty, 4)
		self.assertEqual(invoice.items[0].rate, 100)
		self.assertEqual(invoice.grand_total, 400)
		sheet.reload()
		sheet.sales_invoice = None
		with self.assertRaisesRegex(frappe.ValidationError, "Sales Invoice link"):
			sheet.save()
		sheet.reload()
		with self.assertRaisesRegex(frappe.ValidationError, invoice_name):
			sheet.cancel()
		self.assertEqual(frappe.db.get_value("Crane Timesheet", sheet.name, "docstatus"), 1)

	def test_daily_rate_counts_crane_day_once_across_timesheets(self):
		from jimmy_cranes.billing import generate_sales_invoice

		assignment = self.assignment()
		assignment.assigned_cranes[0].rental_rate = 120
		assignment.assigned_cranes[0].rental_rate_unit = "Day"
		assignment.save()
		self.action(assignment, "Reserve")
		first = self.sheet(entries=[self.shift(day=5, start="08:00:00", end="12:00:00")])
		first.insert().submit()
		second = self.sheet(entries=[self.shift(day=5, start="12:00:00", end="16:00:00")])
		second.insert().submit()
		result = generate_sales_invoice(project=self.project.name)
		invoice = frappe.get_doc("Sales Invoice", result["name"])
		self.assertEqual(invoice.grand_total, 120)
		self.assertEqual(set(result["timesheets"]), {first.name, second.name})
		third = self.sheet(entries=[self.shift(day=5, start="16:00:00", end="20:00:00")])
		third.insert().submit()
		self.assertEqual(generate_sales_invoice(timesheet=third.name)["name"], invoice.name)
		self.assertEqual(frappe.db.get_value("Crane Timesheet", third.name, "sales_invoice"), invoice.name)

	def test_undo_cancel_restores_original_status_and_project_reopens(self):
		assignment = self.assignment(cranes=self.cranes[:2])
		self.action(assignment, "Reserve", [assignment.assigned_cranes[0].name])
		self.action(assignment, "Cancel", reason="Wrong selection")
		self.assertEqual([row.status_before_cancel for row in assignment.assigned_cranes], ["Reserved", "Draft"])
		crane_action(
			assignment.name, self.project.name, [row.name for row in assignment.assigned_cranes],
			"Undo Cancel", reason="Restore both cranes",
		)
		assignment.reload()
		self.assertEqual([row.status for row in assignment.assigned_cranes], ["Reserved", "Draft"])
		self.assertTrue(all(not row.cancellation_date and not row.status_before_cancel for row in assignment.assigned_cranes))
		crane_action(
			assignment.name, self.project.name, [assignment.assigned_cranes[0].name],
			"Undo Reserve", reason="Reservation was premature",
		)
		self.assertEqual(assignment.reload().assigned_cranes[0].status, "Draft")
		self.action(assignment, "Cancel", reason="Close project")
		project_action(self.project.name, "Complete")
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			project_action(self.project.name, "Reopen")
		project_action(self.project.name, "Reopen", reason="Closed by mistake")
		self.assertEqual(self.project.reload().status, "Open")
		comments = frappe.get_all("Comment", filters={"reference_doctype": "Crane Project", "reference_name": self.project.name}, pluck="content")
		self.assertTrue(any("Closed by mistake" in comment for comment in comments))
