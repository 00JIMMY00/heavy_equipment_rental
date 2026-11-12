"""End-to-end checks for the two entry points and direct billing."""

from calendar import monthrange
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from heavy_equipment_rental.billing import generate_crane_sales_invoices, generate_sales_invoice


class TestRentalWorkflow(FrappeTestCase):
    def test_assignment_defaults_use_settings_and_crane_prices(self):
        original = frappe.db.get_single_value("Heavy Equipment Rental Settings", "default_selling_uom")
        try:
            settings = frappe.get_single("Heavy Equipment Rental Settings")
            settings.default_selling_uom = "Day"
            settings.save()
            crane = frappe.get_doc(dict(doctype="Crane", crane_name="Assignment defaults " + frappe.generate_hash(length=8),
                operational_condition="Operational")).insert()
            for row in crane.period_prices:
                row.price = {"Hour": 100, "Day": 700, "Month": 15000}[row.period]
            crane.save()
            day = getdate(today()) + timedelta(days=400)
            assignment = frappe.get_doc(dict(doctype="Crane Assignment",
                customer=frappe.db.get_value("Customer", {}, "name"), location="Defaults test",
                assigned_cranes=[dict(crane=crane.name, start_date=day, expected_end_date=day)])).insert()
            self.assertEqual((assignment.assigned_cranes[0].rental_rate_unit, assignment.assigned_cranes[0].rental_rate), ("Day", 700))
            from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_assignment.crane_assignment import get_assignment_defaults
            self.assertEqual(get_assignment_defaults(crane.name, "Month")["rental_rate"], 15000)
            settings.default_selling_uom = "Month"
            settings.save()
            assignment.save()
            self.assertEqual((assignment.assigned_cranes[0].rental_rate_unit, assignment.assigned_cranes[0].rental_rate), ("Day", 700))
        finally:
            frappe.db.set_single_value("Heavy Equipment Rental Settings", "default_selling_uom", original)

    def test_completed_maintenance_uses_shared_expense_entry(self):
        expense_type = next((row for row in frappe.get_all(
            "Expense Entry Type", filters={"enabled": 1}, fields=["name", "company"],
            limit_page_length=0,
        ) if frappe.db.get_value("Mode of Payment Account", {"company": row.company}, "parent")), None)
        if not expense_type:
            self.skipTest("An enabled Expense Entry Type and Mode of Payment are required")
        mode = frappe.db.get_value("Mode of Payment Account", {"company": expense_type.company}, "parent")
        crane = frappe.get_doc({
            "doctype": "Crane", "crane_name": "Expense test " + frappe.generate_hash(length=8),
            "operational_condition": "Operational",
        }).insert()
        maintenance = frappe.get_doc({
            "doctype": "Crane Maintenance", "crane": crane.name,
            "maintenance_type": "Corrective", "description": "Expense integration test",
            "status": "Planned",
        }).insert()
        maintenance.status = "Completed"
        maintenance.cost = 125
        maintenance.expense_type = expense_type.name
        maintenance.mode_of_payment = mode
        maintenance.save()
        expense = frappe.get_doc("Expense Entry", maintenance.expense_entry)
        self.assertEqual(expense.company, expense_type.company)
        self.assertEqual(expense.crane, crane.name)
        self.assertEqual(expense.docstatus, 1)
        self.assertEqual(expense.expenses[0].expense_entry_type, expense_type.name)
        self.assertEqual(expense.expenses[0].amount, 125)
        self.assertTrue(expense.journal_entry)

    def test_assignment_first_and_timesheet_first(self):
        employee = frappe.db.get_value("Employee", {}, "name")
        other_employee = frappe.db.get_value("Employee", {"name": ["!=", employee]}, "name") if employee else None
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
            "operational_condition": "Operational", "license_plate": "TEST-" + key,
            "crane_image": "/files/test-crane.jpg",
        }).insert()
        self.assertEqual(crane.license_plate, "TEST-" + key)
        self.assertEqual(crane.crane_image, "/files/test-crane.jpg")
        self.assertEqual(crane.crane_list_image, crane.crane_image)
        self.assertEqual([row.period for row in crane.period_prices], ["Hour", "Day", "Month"])
        item = frappe.get_doc("Item", crane.item)
        self.assertEqual(item.image, crane.crane_image)
        self.assertEqual(
            [(row.period, row.price) for row in item.period_prices],
            [(row.period, row.price) for row in crane.period_prices],
        )
        crane.period_prices[0].price = 42
        crane.save()
        self.assertEqual(frappe.get_doc("Item", crane.item).period_prices[0].price, 42)
        crane.crane_image = "/files/updated-test-crane.jpg"
        crane.save()
        self.assertEqual(crane.crane_list_image, crane.crane_image)
        self.assertEqual(frappe.db.get_value("Item", crane.item, "image"), crane.crane_image)
        crane.crane_image = None
        crane.save()
        self.assertFalse(crane.crane_list_image)
        self.assertFalse(frappe.db.get_value("Item", crane.item, "image"))
        crane.crane_image = "/private/files/test-crane.jpg"
        with self.assertRaises(frappe.ValidationError):
            crane.save()
        crane.reload()
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
            "driver": employee,
            "timesheet_entries": [
                {"work_date": day, "start_time": "08:00", "end_time": "12:00"},
                {"work_date": day, "employee": other_employee or employee,
                 "start_time": "10:00", "end_time": "14:00"},
            ],
        }).insert()
        self.assertEqual(sheet.timesheet_entries[0].employee, employee)
        self.assertEqual(sheet.timesheet_entries[1].employee, other_employee or employee)
        self.assertEqual(sum(row.total_hours for row in sheet.driver_hours), 8)
        self.assertTrue(all(row.driver_name for row in sheet.driver_hours))
        self.assertTrue(all(row.driver_name for row in sheet.timesheet_entries))
        sheet.submit()
        sheet.attachment = "/private/files/rental-timesheet-test.pdf"
        sheet.save()
        self.assertEqual(frappe.db.get_value("Crane Timesheet", sheet.name, "attachment"), sheet.attachment)
        self.assertEqual(sheet.customer, customer.name)
        self.assertEqual(sheet.location, "Test yard")
        self.assertEqual(sheet.total_operator_hours, 8)
        self.assertEqual(sheet.total_crane_billable_hours, 6)
        self.assertEqual(sheet.total_amount, 90)
        result = generate_sales_invoice(timesheet=sheet.name)
        invoice = frappe.get_doc("Sales Invoice", result["name"])
        self.assertEqual(invoice.customer, customer.name)
        self.assertEqual(invoice.items[0].rate, 90)
        self.assertEqual((sheet.timesheet_entries[0].rental_rate, sheet.timesheet_entries[0].rental_rate_unit), (90, "Day"))
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
            "location": "Second yard", "period_start": later,
            "period_end": later + timedelta(days=9),
            "rental_rate_unit": "Hour", "rental_rate": 120,
            "timesheet_entries": [{
                "work_date": later, "employee": employee, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        self.assertTrue(first.assignment)
        booking = frappe.get_doc("Crane Assignment", first.assignment).assigned_cranes[0]
        self.assertEqual(getdate(booking.start_date), later)
        self.assertEqual(getdate(booking.expected_end_date), later + timedelta(days=9))
        second_day = later + timedelta(days=1)
        second = frappe.get_doc({
            "doctype": "Crane Timesheet", "crane": crane.name, "customer": customer.name,
            "location": "Second yard", "period_start": second_day, "period_end": second_day,
            "timesheet_entries": [{
                "work_date": second_day, "employee": employee, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        self.assertEqual(second.assignment, first.assignment)
        first.timesheet_entries[0].worked_hours = 0
        first.save()
        self.assertEqual(first.timesheet_entries[0].worked_hours, 0)
        self.assertEqual(first.total_crane_billable_hours, 0)
        first.timesheet_entries[0].worked_hours = 2
        first.save()
        first.timesheet_entries[0].end_time = "14:00"
        first.save()
        self.assertEqual(first.timesheet_entries[0].worked_hours, 2)
        self.assertEqual(first.total_crane_billable_hours, 2)
        self.assertEqual(first.total_amount, 240)
        first.submit()
        hourly_invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=first.name)["name"])
        self.assertEqual(hourly_invoice.items[0].qty, 2)
        self.assertEqual(hourly_invoice.items[0].rate, 120)
        self.assertEqual((first.timesheet_entries[0].rental_rate, first.timesheet_entries[0].rental_rate_unit), (120, "Hour"))
        monthly_day = later + timedelta(days=20)
        monthly = frappe.get_doc({
            "doctype": "Crane Timesheet", "crane": crane.name, "customer": customer.name,
            "location": "Monthly yard", "period_start": monthly_day,
            "period_end": monthly_day + timedelta(days=9),
            "rental_rate_unit": "Month", "rental_rate": 930,
            "timesheet_entries": [{
                "work_date": monthly_day, "employee": employee, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        monthly.submit()
        self.assertEqual((monthly.timesheet_entries[0].rental_rate, monthly.timesheet_entries[0].rental_rate_unit), (930, "Month"))
        monthly_invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=monthly.name)["name"])
        self.assertAlmostEqual(monthly_invoice.items[0].rate,
                               930 / monthrange(monthly_day.year, monthly_day.month)[1], delta=0.02)
        second.submit()
        next_monthly_day = monthly_day + timedelta(days=1)
        monthly_followup = frappe.get_doc({
            "doctype": "Crane Timesheet", "assignment": monthly.assignment,
            "crane": crane.name, "period_start": next_monthly_day, "period_end": next_monthly_day,
            "timesheet_entries": [{
                "work_date": next_monthly_day, "employee": employee,
                "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        monthly_followup.submit()
        created = generate_crane_sales_invoices(crane.name)
        self.assertEqual(len(created["invoices"]), 2)
        self.assertTrue(all(
            all(row.item_code == crane.item for row in frappe.get_doc("Sales Invoice", name).items)
            for name in created["invoices"]
        ))
        self.assertTrue(frappe.db.get_value("Crane Timesheet", second.name, "sales_invoice"))
        self.assertTrue(frappe.db.get_value("Crane Timesheet", monthly_followup.name, "sales_invoice"))
        self.assertFalse(generate_crane_sales_invoices(crane.name)["invoices"])
