"""Real concurrent connections: one booking/submission wins, never both."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import frappe
from frappe.tests.utils import FrappeTestCase

from jimmy_cranes.jimmy_cranes.doctype.crane_assignment import test_crane_assignment as fixtures
from jimmy_cranes.rental_operations import crane_action


class TestRentalConcurrency(FrappeTestCase):
	def test_overlapping_writes_are_serialized(self):
		sample = fixtures.TestCraneRental()
		sample.setUp()
		first = sample.assignment()
		second = sample.assignment(project=sample.other_project)
		sheets = []
		site, sites_path = frappe.local.site, frappe.local.sites_path
		all_docs = {
			"Crane Assignment": [first.name, second.name],
			"Crane Project": [sample.project.name, sample.other_project.name],
			"Crane": [r.name for r in sample.cranes],
			"Crane Operator": [r.name for r in sample.operators],
			"Customer": [sample.customer.name],
		}
		frappe.db.commit()

		def run_concurrent(kind, items):
			barrier = Barrier(2)

			def worker(item):
				frappe.init(site=site, sites_path=sites_path)
				frappe.connect()
				frappe.set_user("Administrator")
				try:
					frappe.db.sql("SET SESSION innodb_lock_wait_timeout=10")
					# Establish a repeatable-read snapshot BEFORE the other writer
					# commits. The authoritative checks must use current reads.
					frappe.db.sql(
						"SELECT name FROM `tabAssigned Crane` WHERE crane=%s", sample.cranes[0].name
					)
					barrier.wait(timeout=10)
					if kind == "booking":
						crane_action(item.name, item.project, [item.assigned_cranes[0].name], "Reserve")
					else:
						frappe.get_doc("Crane Timesheet", item.name).submit()
					frappe.db.commit()
					return "saved"
				except (frappe.ValidationError, frappe.QueryDeadlockError):
					frappe.db.rollback()
					return "rejected"
				finally:
					frappe.destroy()

			with ThreadPoolExecutor(max_workers=2) as pool:
				return list(pool.map(worker, items))

		try:
			self.assertEqual(sorted(run_concurrent("booking", [first, second])), ["rejected", "saved"])
			frappe.db.rollback()
			booked = frappe.get_all(
				"Assigned Crane",
				filters={"parent": ["in", [first.name, second.name]], "status": "Reserved"},
				pluck="parent",
			)
			self.assertEqual(len(booked), 1)
			project = frappe.db.get_value("Crane Assignment", booked[0], "project")
			sheet_project = sample.project if project == sample.project.name else sample.other_project
			sheets = [sample.sheet(project=sheet_project).insert() for _ in range(2)]
			all_docs["Crane Timesheet"] = [s.name for s in sheets]
			frappe.db.commit()
			self.assertEqual(sorted(run_concurrent("submission", sheets)), ["rejected", "saved"])
			frappe.db.rollback()
			self.assertEqual(
				frappe.db.count(
					"Crane Timesheet", {"name": ["in", [s.name for s in sheets]], "docstatus": 1}
				),
				1,
			)
		finally:
			frappe.db.rollback()
			# Only these explicitly created fixtures are removed, including the
			# committed winner. Never use force-delete on real rental history.
			for child, parents in [
				("Timesheet Entry", all_docs.get("Crane Timesheet", [])),
				("Assigned Crane", all_docs["Crane Assignment"]),
				("Crane Period Price", all_docs["Crane"]),
			]:
				if parents:
					frappe.db.delete(child, {"parent": ["in", parents]})
			for doctype, names in all_docs.items():
				frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
				frappe.db.delete(doctype, {"name": ["in", names]})
			frappe.db.commit()
