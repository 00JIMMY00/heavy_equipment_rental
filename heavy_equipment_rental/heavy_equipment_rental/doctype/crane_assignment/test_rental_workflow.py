"""End-to-end checks for the two entry points and direct billing."""

from calendar import monthrange
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from heavy_equipment_rental.billing import generate_sales_invoice


class TestRentalWorkflow(FrappeTestCase):
    def test_assignment_first_and_timesheet_first(self):
        employee = frappe.db.get_value("Employee", {}, "name")
        group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
        territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
        if not all((employee, group, territory)):
            self.skipTest("Employee, Customer Group and Territory are required")
        key = frappe.generate_hash(length=8)
        customer = frappe.get_doc({
            "doctype": "Customer", "customer_name": "Rental test " + key,
            "customer_type": "Company", "customer_group": group, "territory": territory,
        }).insert()
        crane = frappe.get_doc({
            "doctype": "Crane", "crane_name": "Rental test crane " + key,
            "operational_condition": "Operational",
        }).insert()
        start = getdate(today()) - timedelta(days=120)
        day = start + timedelta(days=1)
        end = start + timedelta(days=9)
        rental = frappe.get_doc({
            "doctype": "Crane Assignment", "customer": customer.name, "location": "Test yard",
            "assigned_cranes": [{
                "crane": crane.name, "start_date": start, "expected_end_date": end,
                "rental_rate_unit": "Day", "rental_rate": 90,
            }],
        }).insert()
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Crane Assignment", "customer": customer.name, "location": "Other yard",
                "assigned_cranes": [{
                    "crane": crane.name, "start_date": day, "expected_end_date": end,
                    "rental_rate_unit": "Hour", "rental_rate": 50,
                }],
            }).insert()
        sheet = frappe.get_doc({
            "doctype": "Crane Timesheet", "assignment": rental.name,
            "crane": crane.name, "period_start": day, "period_end": day,
            "timesheet_entries": [
                {"work_date": day, "employee": employee, "start_time": "08:00", "end_time": "12:00"},
                {"work_date": day, "employee": employee, "start_time": "10:00", "end_time": "14:00"},
            ],
        }).insert()
        sheet.submit()
        self.assertEqual(sheet.customer, customer.name)
        self.assertEqual(sheet.location, "Test yard")
        self.assertEqual(sheet.total_operator_hours, 8)
        self.assertEqual(sheet.total_crane_billable_hours, 6)
        self.assertEqual(sheet.total_amount, 90)
        result = generate_sales_invoice(timesheet=sheet.name)
        invoice = frappe.get_doc("Sales Invoice", result["name"])
        self.assertEqual(invoice.customer, customer.name)
        self.assertEqual(invoice.items[0].rate, 90)
        self.assertFalse(invoice.items[0].sales_order)
        same_day = frappe.get_doc({
            "doctype": "Crane Timesheet", "assignment": rental.name, "crane": crane.name,
            "period_start": day, "period_end": day,
            "timesheet_entries": [{
                "work_date": day, "employee": employee, "start_time": "15:00", "end_time": "16:00",
            }],
        }).insert()
        same_day.submit()
        self.assertTrue(generate_sales_invoice(timesheet=same_day.name)["already_exists"])
        later = start + timedelta(days=20)
        first = frappe.get_doc({
            "doctype": "Crane Timesheet", "crane": crane.name, "customer": customer.name,
            "location": "Second yard", "period_start": later, "period_end": later,
            "rental_start_date": later, "rental_end_date": later + timedelta(days=9),
            "rental_rate_unit": "Hour", "rental_rate": 120,
            "timesheet_entries": [{
                "work_date": later, "employee": employee, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        self.assertTrue(first.assignment)
        second_day = later + timedelta(days=1)
        second = frappe.get_doc({
            "doctype": "Crane Timesheet", "crane": crane.name, "customer": customer.name,
            "location": "Second yard", "period_start": second_day, "period_end": second_day,
            "timesheet_entries": [{
                "work_date": second_day, "employee": employee, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        self.assertEqual(second.assignment, first.assignment)
        first.submit()
        hourly_invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=first.name)["name"])
        self.assertEqual(hourly_invoice.items[0].qty, 4)
        self.assertEqual(hourly_invoice.items[0].rate, 120)
        monthly_day = later + timedelta(days=20)
        monthly = frappe.get_doc({
            "doctype": "Crane Timesheet", "crane": crane.name, "customer": customer.name,
            "location": "Monthly yard", "period_start": monthly_day, "period_end": monthly_day,
            "rental_start_date": monthly_day, "rental_end_date": monthly_day + timedelta(days=9),
            "rental_rate_unit": "Month", "rental_rate": 930,
            "timesheet_entries": [{
                "work_date": monthly_day, "employee": employee, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        monthly.submit()
        monthly_invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=monthly.name)["name"])
        self.assertAlmostEqual(monthly_invoice.items[0].rate,
                               930 / monthrange(monthly_day.year, monthly_day.month)[1], delta=0.02)
