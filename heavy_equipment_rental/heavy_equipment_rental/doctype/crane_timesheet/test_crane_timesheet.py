"""Rented crane purchasing uses native ERPNext invoices and payments."""

from calendar import monthrange
from datetime import timedelta

import erpnext
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.cancellation import cancel_all, cancellation_plan
from heavy_equipment_rental.payment import payment_account
from heavy_equipment_rental.purchasing import (
    create_purchase_invoice,
    make_supplier_payment,
    supplier_payment_invoices,
)


class TestCraneTimesheet(FrappeTestCase):
    def setUp(self):
        self.key = frappe.generate_hash(length=8)
        for name in ["Supplier test yard " + self.key, "Default terms " + self.key,
                     "Override defaults " + self.key] + ["Unit test yard " + unit + self.key for unit in ("Hour", "Day", "Month")]:
            frappe.get_doc({"doctype": "Location", "location_name": name}).insert()
        self.company = erpnext.get_default_company()
        self.employee = frappe.db.get_value("Employee", {}, "name")
        self.assertTrue(self.company and self.employee, "Development tests need a Company and Employee")
        self.supplier = frappe.get_doc({
            "doctype": "Supplier", "supplier_name": "Rental supplier " + self.key,
            "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
            "supplier_type": "Company",
        }).insert()
        self.customer = frappe.get_doc({
            "doctype": "Customer", "customer_name": "Rental customer " + self.key,
            "customer_type": "Company",
            "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
            "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
        }).insert()
        self.crane = frappe.get_doc({
            "doctype": "Crane", "crane_name": "Rented crane " + self.key,
            "hired_from_supplier": 1, "supplier": self.supplier.name,
            "operational_condition": "Operational",
        }).insert()
        self.day = getdate(today()) - timedelta(days=120)
        self.assignment = frappe.get_doc({
            "doctype": "Rental Contract", "company": self.company,
            "customer": self.customer.name, "location": "Supplier test yard " + self.key,
            "assigned_cranes": [{
                "crane": self.crane.name, "start_date": self.day,
                "expected_end_date": self.day + timedelta(days=10),
                "rental_rate_unit": "Hour", "rental_rate": 100,
            }],
        }).insert()

    def make_sheet(self, offset=0, rate=25, length=1, assignment=None):
        day = self.day + timedelta(days=offset)
        return frappe.get_doc({
            "doctype": "Crane Timesheet", "assignment": assignment or self.assignment.name,
            "crane": self.crane.name, "period_start": day, "period_end": day + timedelta(days=length-1),
            "purchase_rate": rate,
            "driver": self.employee,
            "timesheet_entries": [{"work_date": day, "start_time": "08:00", "end_time": "12:00"}],
        })

    def set_billing_defaults(self, selling="Hour", supplier="Hour"):
        settings = frappe.get_single("Heavy Equipment Rental Settings")
        original = {field: settings.get(field) for field in ("default_selling_uom", "default_supplier_uom")}
        self.addCleanup(frappe.db.set_single_value, settings.doctype, original)
        settings.default_selling_uom, settings.default_supplier_uom = selling, supplier
        settings.save()

    def make_payroll_driver(self):
        return frappe.get_doc({
            "doctype": "Employee", "first_name": "Payroll driver " + self.key,
            "company": self.company, "gender": "Male", "date_of_birth": "1980-01-01",
            "date_of_joining": self.day, "status": "Active",
        }).insert().name

    def test_driver_payroll_posts_once_per_driver_and_cancels_with_timesheet(self):
        settings = frappe.get_single("Heavy Equipment Rental Settings")
        expense_type = frappe.db.get_value("Expense Entry Type", {
            "company": self.company, "enabled": 1,
        }, ["name", "account"], as_dict=True)
        mode = frappe.db.get_value("Mode of Payment Account", {"company": self.company}, "parent")
        settings.set("driver_payroll_defaults", [{
            "company": self.company, "expense_type": expense_type.name, "mode_of_payment": mode,
        }])
        settings.save()

        sheet = self.make_sheet()
        sheet.rented = 0
        sheet.driver = frappe.db.get_value("Employee", {"company": self.company}, "name")
        second_driver, unpaid_driver = self.make_payroll_driver(), self.make_payroll_driver()
        for employee in (second_driver, unpaid_driver):
            sheet.append("timesheet_entries", {
                "work_date": self.day, "start_time": "08:00", "end_time": "12:00", "employee": employee,
            })
        sheet.append("timesheet_entries", {
            "work_date": self.day, "start_time": "12:00", "end_time": "14:00",
            "employee": sheet.driver,
        })
        sheet.insert()
        self.assertEqual([row.employee for row in sheet.driver_payroll], [sheet.driver, second_driver, unpaid_driver])
        self.assertEqual([row.quantity for row in sheet.driver_payroll], [6, 4, 4])
        sheet.driver_payroll[0].rate = 25
        sheet.driver_payroll[1].amount = 75
        sheet.save()
        self.assertEqual([flt(row.amount) for row in sheet.driver_payroll], [150, 75, 0])
        self.assertFalse(frappe.db.exists("Expense Entry", {"crane_timesheet": sheet.name}))

        sheet.submit()
        sheet.reload()
        self.assertFalse(sheet.driver_payroll[2].expense_entry)
        expenses = {}
        for row in sheet.driver_payroll[:2]:
            expense = frappe.get_doc("Expense Entry", row.expense_entry)
            expenses[expense.name] = expense.journal_entry
            self.assertEqual(expense.docstatus, 1)
            self.assertEqual(expense.employee, row.employee)
            self.assertEqual(expense.company, self.company)
            self.assertEqual(expense.crane_timesheet, sheet.name)
            self.assertEqual(expense.crane_assignment, sheet.assignment)
            self.assertEqual(expense.crane, sheet.crane)
            self.assertEqual(getdate(expense.posting_date), getdate(today()))
            journal = frappe.get_doc("Journal Entry", expense.journal_entry)
            self.assertEqual(journal.docstatus, 1)
            debit, credit = journal.accounts
            self.assertEqual((debit.account, debit.party_type, debit.party), (expense_type.account, "Employee", row.employee))
            self.assertEqual((credit.account, credit.credit), (payment_account(mode, self.company), row.amount))
            self.assertEqual(debit.debit, row.amount)
        self.assertEqual(frappe.db.count("Expense Entry", {"crane_timesheet": sheet.name}), 2)

        from heavy_equipment_rental.patches.backfill_driver_payroll_quantities import execute

        first, second, unpaid = sheet.driver_payroll
        frappe.db.set_value("Crane Driver Payroll", first.name, {"unit": None, "quantity": 0})
        frappe.db.set_value("Crane Driver Payroll", second.name, {"unit": None, "quantity": 0})
        frappe.db.delete("Crane Driver Payroll", {"name": unpaid.name})
        execute()
        execute()
        sheet.reload()
        self.assertEqual([flt(row.amount) for row in sheet.driver_payroll], [150, 75, 0])
        self.assertEqual([row.quantity for row in sheet.driver_payroll], [6, 4, 4])
        self.assertTrue(all(row.docstatus == 1 for row in sheet.driver_payroll))
        self.assertEqual([row.expense_entry for row in sheet.driver_payroll[:2]], list(expenses))
        self.assertEqual(sheet.driver_payroll[1].rate, flt(75 / 4, sheet.driver_payroll[1].precision("rate")))

        sheet.attachment = "/private/files/payroll-test.pdf"
        sheet.save()
        self.assertEqual(frappe.db.count("Expense Entry", {"crane_timesheet": sheet.name}), 2)
        with self.assertRaisesRegex(frappe.ValidationError, "Cancel Crane Timesheet"):
            cancellation_plan("Expense Entry", next(iter(expenses)))
        plan = cancellation_plan(sheet.doctype, sheet.name)
        self.assertEqual({row["name"] for row in plan if row["doctype"] == "Expense Entry"}, set(expenses))
        cancel_all(sheet.doctype, sheet.name, plan)
        self.assertEqual(sheet.reload().docstatus, 2)
        for expense, journal in expenses.items():
            self.assertEqual(frappe.db.get_value("Expense Entry", expense, "docstatus"), 2)
            self.assertEqual(frappe.db.get_value("Journal Entry", journal, "docstatus"), 2)

        amendment = frappe.copy_doc(sheet, ignore_no_copy=False)
        amendment.docstatus = 0
        amendment.amended_from = sheet.name
        amendment.insert()
        self.assertEqual([flt(row.amount) for row in amendment.driver_payroll], [150, 75, 0])
        self.assertFalse(any(row.expense_entry for row in amendment.driver_payroll))
        amendment.submit()
        self.assertTrue(all(row.expense_entry not in expenses for row in amendment.driver_payroll[:2]))

    def test_driver_payroll_quantity_follows_selling_unit_and_manual_amount(self):
        sheet = self.make_sheet(length=4)
        sheet.rented = 0
        sheet.driver = frappe.db.get_value("Employee", {"company": self.company}, "name")
        for offset, start, end, next_day, hours in (
            (0, "10:00", "12:00", 0, 2),
            (1, "22:00", "02:00", 1, 4),
            (2, "22:00", "00:00", 1, 2),
            (3, "08:00", "12:00", 0, 0),
        ):
            sheet.append("timesheet_entries", {
                "work_date": self.day + timedelta(days=offset), "start_time": start, "end_time": end,
                "ends_next_day": next_day, "worked_hours": hours,
            })
        sheet.insert()
        payroll = sheet.driver_payroll[0]
        self.assertEqual((payroll.unit, payroll.quantity, payroll.worked_hours), ("Hour", 12, 12))
        payroll.rate = 50
        sheet.rental_rate_unit = "Day"
        sheet.save()
        self.assertEqual((payroll.unit, payroll.quantity, payroll.amount), ("Day", 3, 150))

        sheet.rental_rate_unit = "Month"
        sheet.save()
        expected_months = sum(1 / monthrange(day.year, day.month)[1]
                              for day in (self.day + timedelta(days=offset) for offset in range(3)))
        self.assertEqual(payroll.unit, "Month")
        self.assertAlmostEqual(payroll.quantity, expected_months, places=9)
        self.assertEqual(payroll.amount, flt(expected_months * 50, payroll.precision("amount")))

        payroll.rate, payroll.amount = 0, 123
        sheet.rental_rate_unit = "Hour"
        sheet.timesheet_entries[0].worked_hours = 5
        sheet.save()
        self.assertEqual((payroll.unit, payroll.quantity, payroll.amount), ("Hour", 13, 123))
        self.assertEqual(payroll.rate, flt(123 / 13, payroll.precision("rate")))
        sheet.reload()
        sheet.timesheet_entries[0].worked_hours = 7
        sheet.save()
        payroll = sheet.driver_payroll[0]
        self.assertEqual((payroll.quantity, payroll.fixed_amount, payroll.amount), (15, 1, 123))
        self.assertEqual(payroll.rate, flt(123 / 15, payroll.precision("rate")))

    def test_optional_payroll_defaults_and_driver_validation(self):
        settings = frappe.get_single("Heavy Equipment Rental Settings")
        settings.set("driver_payroll_defaults", [])
        settings.save()
        sheet = self.make_sheet()
        sheet.rented = 0
        sheet.driver = frappe.db.get_value("Employee", {"company": self.company}, "name")
        sheet.insert()
        sheet.driver_payroll[0].amount = -1
        with self.assertRaisesRegex(frappe.ValidationError, "non-negative amount"):
            sheet.save()
        sheet.reload()
        sheet.driver_payroll[0].amount = 125
        sheet.save()
        frappe.db.savepoint("missing_payroll_defaults")
        with self.assertRaisesRegex(frappe.ValidationError, "Set driver payroll defaults"):
            sheet.submit()
        frappe.db.rollback(save_point="missing_payroll_defaults")
        self.assertEqual(sheet.reload().docstatus, 0)
        self.assertFalse(frappe.db.exists("Expense Entry", {"crane_timesheet": sheet.name}))
        sheet.timesheet_entries[0].employee = self.make_payroll_driver()
        replacement_driver = sheet.timesheet_entries[0].employee
        with self.assertRaisesRegex(frappe.ValidationError, "Clear the amount"):
            sheet.save()
        sheet.reload()
        sheet.timesheet_entries[0].employee = replacement_driver
        sheet.driver_payroll[0].amount = 0
        sheet.save()
        self.assertEqual([row.employee for row in sheet.driver_payroll], [sheet.timesheet_entries[0].employee])
        sheet.submit()
        self.assertFalse(frappe.db.exists("Expense Entry", {"crane_timesheet": sheet.name}))

    def test_delete_draft_sales_invoice_releases_timesheet(self):
        from heavy_equipment_rental.billing import generate_sales_invoice
        sheet = self.make_sheet().insert().submit()
        name = generate_sales_invoice(timesheet=sheet.name)["name"]
        frappe.delete_doc("Sales Invoice", name)
        self.assertFalse(frappe.db.exists("Sales Invoice", name))
        self.assertFalse(sheet.reload().sales_invoice)
        self.assertEqual(sheet.docstatus, 1)
        replacement = generate_sales_invoice(timesheet=sheet.name)["name"]
        self.assertTrue(frappe.db.exists("Sales Invoice", replacement))

    def test_editable_selling_terms_reach_invoice_without_changing_assignment(self):
        from heavy_equipment_rental.billing import generate_sales_invoice
        from heavy_equipment_rental.heavy_equipment_rental.doctype.rental_contract.rental_contract import get_assignment_defaults
        self.crane.default_selling_uom = "Day"
        self.crane.period_prices[1].price = 1500
        self.crane.save()
        self.assertEqual(get_assignment_defaults(self.crane.name)["rental_rate_unit"], "Day")
        self.assertEqual(get_assignment_defaults(self.crane.name, "Hour")["rental_rate_unit"], "Hour")
        sheet = self.make_sheet().insert()
        self.assertEqual(sheet.rental_rate_unit, "Hour")
        sheet.rental_rate_unit, sheet.rental_rate = "Day", 1500
        sheet.save()
        sheet.reload()
        self.assertEqual((sheet.rental_rate_unit, sheet.rental_rate), ("Day", 1500))
        self.assertEqual(sheet.total_amount, 1500)
        self.assertEqual(sheet.timesheet_entries[0].rental_rate_unit, "Day")
        sheet.submit()
        invoice = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=sheet.name)["name"])
        self.assertEqual((invoice.items[0].uom, invoice.items[0].qty, invoice.items[0].rate), ("Day", 1, 1500))
        self.assertEqual(invoice.items[0].stock_qty, 4)
        self.assertEqual(self.assignment.reload().assigned_cranes[0].rental_rate_unit, "Hour")
        invoice.items[0].rate = 1600
        invoice.save()
        self.assertEqual(invoice.reload().items[0].rate, 1600)
        conflicting = self.make_sheet()
        conflicting.rental_rate_unit, conflicting.rental_rate = "Day", 2000
        conflicting.timesheet_entries[0].start_time = "15:00"
        conflicting.timesheet_entries[0].end_time = "16:00"
        conflicting.insert().submit()
        with self.assertRaises(frappe.ValidationError):
            generate_sales_invoice(timesheet=conflicting.name)

        from heavy_equipment_rental.patches.crane_default_selling_uom import execute
        execute()
        self.assertEqual(self.crane.reload().default_selling_uom, "Day")
        self.assertEqual(sheet.reload().rental_rate_unit, "Day")
        self.assertEqual(invoice.reload().items[0].rate, 1600)

    def test_new_timesheet_defaults_create_assignment_and_preserve_snapshot(self):
        from heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet import get_timesheet_defaults

        self.set_billing_defaults(selling="Day", supplier="Month")
        self.crane.default_selling_uom = "Day"
        self.crane.period_prices[1].price = 350
        self.crane.save()
        defaults = get_timesheet_defaults(self.crane.name)
        self.assertEqual(defaults, {"rental_rate_unit": "Day", "rental_rate": 350, "purchase_uom": "Month"})
        day = self.day + timedelta(days=20)
        sheet = frappe.get_doc({
            "doctype": "Crane Timesheet", "crane": self.crane.name,
            "customer": self.customer.name, "location": "Default terms " + self.key,
            "period_start": day, "period_end": day, "driver": self.employee,
            "purchase_rate": 900, "timesheet_entries": [{
                "work_date": day, "start_time": "08:00", "end_time": "12:00",
            }],
        }).insert()
        self.assertEqual(sheet.rental_rate_unit, "Day")
        self.assertEqual(sheet.rental_rate, 350)
        self.assertEqual(sheet.purchase_uom, "Month")
        booking = frappe.get_doc("Rental Contract", sheet.assignment).assigned_cranes[0]
        self.assertEqual((booking.rental_rate_unit, booking.rental_rate), ("Day", 350))
        frappe.db.set_single_value("Heavy Equipment Rental Settings", {
            "default_selling_uom": "Hour", "default_supplier_uom": "Hour",
        })
        sheet.save()
        sheet.submit()
        invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
        self.assertEqual(invoice.items[0].uom, "Month")
        self.assertAlmostEqual(invoice.items[0].qty, 1 / monthrange(day.year, day.month)[1], places=5)
        self.assertAlmostEqual(invoice.items[0].stock_qty, 4, places=3)
        self.assertEqual((sheet.rental_rate_unit, sheet.rental_rate), ("Day", 350))

    def test_assignment_and_explicit_terms_override_settings(self):
        self.set_billing_defaults(selling="Month", supplier="Day")
        linked = self.make_sheet().insert()
        self.assertEqual((linked.rental_rate_unit, linked.rental_rate), ("Hour", 100))
        self.assertEqual(linked.purchase_uom, "Day")
        explicit = self.make_sheet(offset=20)
        explicit.assignment = None
        explicit.customer = self.customer.name
        explicit.location = "Override defaults " + self.key
        explicit.rental_rate_unit, explicit.rental_rate = "Hour", 123
        explicit.purchase_uom = "Hour"
        explicit.insert()
        self.assertEqual((explicit.rental_rate_unit, explicit.rental_rate), ("Hour", 123))
        self.assertEqual(explicit.purchase_uom, "Hour")

    def test_supplier_day_and_month_use_worked_dates_not_period_span(self):
        self.set_billing_defaults(supplier="Day")
        for offset, unit in ((0, "Day"), (5, "Month")):
            frappe.db.set_single_value("Heavy Equipment Rental Settings", "default_supplier_uom", unit)
            sheet = self.make_sheet(offset=offset, length=4, rate=900)
            day = self.day + timedelta(days=offset)
            sheet.append("timesheet_entries", {"work_date": day, "employee": self.employee,
                "start_time": "10:00", "end_time": "14:00"})
            sheet.append("timesheet_entries", {"work_date": day + timedelta(days=2), "employee": self.employee,
                "start_time": "08:00", "end_time": "10:00"})
            sheet.insert()
            sheet.submit()
            invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
            expected = 2 if unit == "Day" else sum(1 / monthrange(date.year, date.month)[1]
                for date in (day, day + timedelta(days=2)))
            self.assertEqual(invoice.items[0].uom, unit)
            self.assertAlmostEqual(invoice.items[0].qty, expected, places=5)
            self.assertAlmostEqual(invoice.items[0].amount, expected * 900, delta=0.02)
            self.assertAlmostEqual(invoice.items[0].stock_qty, 8, places=3)
            self.assertEqual(sheet.rental_rate_unit, "Hour")

    def test_uom_migration_preserves_existing_terms_and_settings(self):
        from heavy_equipment_rental.patches.default_timesheet_billing_uoms import execute

        self.set_billing_defaults(selling="Month", supplier="Day")
        old = self.make_sheet().insert()
        old.purchase_uom = "Hour"
        old.submit()
        invoice = frappe.get_doc("Purchase Invoice", old.purchase_invoice)
        draft = self.make_sheet(offset=1).insert()
        frappe.db.set_value("Crane Timesheet", old.name, "purchase_uom", None, update_modified=False)
        frappe.db.set_value("Crane Timesheet", draft.name, "purchase_uom", None, update_modified=False)
        execute()
        old.reload()
        draft.reload()
        self.assertEqual(old.purchase_uom, "Hour")
        self.assertEqual(draft.purchase_uom, "Hour")
        self.assertEqual(draft.purchase_rate, 25)
        draft.purchase_uom = "Month"
        draft.save()
        execute()
        draft.reload()
        invoice.reload()
        self.assertEqual(draft.purchase_uom, "Month")
        self.assertEqual(invoice.items[0].uom, "Hour")
        self.assertEqual(invoice.items[0].amount, 100)
        self.assertEqual(frappe.db.get_single_value("Heavy Equipment Rental Settings", "default_supplier_uom"), "Day")

    def test_invoice_posting_units_payments_and_cancellation(self):
        monthly_start = (self.day + timedelta(days=60)).replace(day=1)
        month_days = monthrange(monthly_start.year, monthly_start.month)[1]
        cases = ((0, "Hour", 1, 4, 25), (20, "Day", 4, 4, 25),
                 ((monthly_start - self.day).days, "Month", month_days, 4, 25))
        for offset, unit, length, qty, rate in cases:
            assignment = self.assignment
            if offset:
                assignment = frappe.get_doc({
                    "doctype": "Rental Contract", "company": self.company,
                    "customer": self.customer.name, "location": "Unit test yard " + unit + self.key,
                    "assigned_cranes": [{
                        "crane": self.crane.name, "start_date": self.day + timedelta(days=offset),
                        "expected_end_date": self.day + timedelta(days=offset+length+2),
                        "rental_rate_unit": unit, "rental_rate": 100,
                    }],
                }).insert()
            sheet = self.make_sheet(offset, rate, length, assignment.name).insert()
            self.assertFalse(sheet.purchase_invoice)
            self.assertEqual(sheet.purchase_supplier, self.supplier.name)
            sheet.submit()
            invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
            self.assertEqual(invoice.docstatus, 1)
            self.assertEqual(invoice.supplier, self.supplier.name)
            self.assertEqual(invoice.company, self.company)
            self.assertEqual(invoice.currency, frappe.get_cached_value("Company", self.company, "default_currency"))
            self.assertEqual(sheet.rental_rate_unit, unit)
            self.assertEqual(invoice.items[0].item_code, self.crane.item)
            self.assertEqual(invoice.items[0].uom, "Hour")
            self.assertAlmostEqual(invoice.items[0].qty, qty)
            self.assertAlmostEqual(invoice.items[0].rate, rate)
            self.assertEqual(sheet.rented, 1)
            self.assertAlmostEqual(invoice.items[0].qty, sheet.total_crane_billable_hours)
            self.assertEqual(invoice.items[0].conversion_factor, 1)
            self.assertAlmostEqual(invoice.items[0].stock_qty, qty, places=3)
            self.assertAlmostEqual(invoice.items[0].amount, qty * rate)
            self.assertIn("Hour", invoice.items[0].description)
            self.assertTrue(frappe.db.exists("GL Entry", {"voucher_type": "Purchase Invoice", "voucher_no": invoice.name}))
            self.assertEqual(create_purchase_invoice(sheet), invoice.name)
            sheet.attachment = "/private/files/purchase-test.pdf"
            sheet.save()
            self.assertEqual(sheet.purchase_invoice, invoice.name)
            candidates = supplier_payment_invoices("Crane Timesheet", sheet.name)
            self.assertEqual([row.name for row in candidates], [invoice.name])
            payment = make_supplier_payment("Crane Timesheet", sheet.name, invoice.name)
            self.assertTrue(payment.is_new())
            self.assertEqual(payment.docstatus, 0)
            self.assertEqual(payment.payment_type, "Pay")
            self.assertEqual(payment.party, self.supplier.name)
            self.assertEqual(payment.references[0].reference_name, invoice.name)
            self.assertAlmostEqual(payment.references[0].allocated_amount, invoice.outstanding_amount)
            self.assertIn(invoice.name, [row.name for row in supplier_payment_invoices("Crane", self.crane.name)])
            with self.assertRaises(frappe.ValidationError):
                sheet.cancel()
            sheet.reload()
            invoice.cancel()
            self.assertFalse(supplier_payment_invoices("Crane Timesheet", sheet.name))
            sheet.cancel()
            self.assertEqual(sheet.docstatus, 2)
            self.assertEqual(sheet.purchase_invoice, invoice.name)
            if offset == 0:
                amendment = frappe.copy_doc(sheet, ignore_no_copy=False)
                amendment.docstatus = 0
                amendment.amended_from = sheet.name
                amendment.insert()
                amendment.submit()
                self.assertNotEqual(amendment.purchase_invoice, invoice.name)
                self.assertEqual(frappe.db.get_value("Purchase Invoice", amendment.purchase_invoice, "docstatus"), 1)

    def test_supplier_terms_and_invoice_link_are_validated(self):
        self.crane.supplier = None
        with self.assertRaises(frappe.ValidationError):
            self.crane.save()
        self.crane.reload()
        for values in ({"purchase_rate": 0}, {"purchase_rate": -1},
                       {"purchase_invoice": "FAKE-INVOICE"}):
            sheet = self.make_sheet()
            sheet.update(values)
            with self.assertRaises(frappe.ValidationError):
                sheet.insert()
        sheet = self.make_sheet().insert()
        sheet.submit()
        invoice_name = sheet.purchase_invoice
        sheet.purchase_invoice = None
        with self.assertRaises(frappe.ValidationError):
            sheet.save()
        other = self.make_sheet(offset=1).insert()
        with self.assertRaises(frappe.ValidationError):
            make_supplier_payment("Crane Timesheet", other.name, invoice_name)

    def test_paid_invoice_is_not_offered_for_payment(self):
        sheet = self.make_sheet().insert()
        sheet.submit()
        payment = make_supplier_payment("Crane", self.crane.name, sheet.purchase_invoice)
        payment.reference_no = "Supplier payment test " + self.key
        payment.reference_date = today()
        payment.insert()
        payment.submit()
        self.assertAlmostEqual(frappe.db.get_value("Purchase Invoice", sheet.purchase_invoice, "outstanding_amount"), 0)
        self.assertFalse(supplier_payment_invoices("Crane", self.crane.name))
        with self.assertRaises(frappe.ValidationError):
            make_supplier_payment("Crane", self.crane.name, sheet.purchase_invoice)

    def test_purchase_permissions_are_required(self):
        sheet = self.make_sheet().insert()
        user = frappe.get_doc({
            "doctype": "User", "email": "rental-purchase-" + self.key + "@example.com",
            "first_name": "Rental purchase test", "send_welcome_email": 0,
            "roles": [{"role": "Projects User"}],
        }).insert()
        frappe.db.savepoint("purchase_permission_test")
        try:
            frappe.set_user(user.name)
            with self.assertRaises(frappe.PermissionError):
                sheet.submit()
        finally:
            frappe.set_user("Administrator")
            frappe.db.rollback(save_point="purchase_permission_test")
        sheet.reload()
        self.assertEqual(sheet.docstatus, 0)
        self.assertFalse(sheet.purchase_invoice)

    def test_periods_can_overlap_but_worked_shifts_cannot(self):
        sheet = self.make_sheet(length=4).insert()
        sheet.submit()
        self.assertEqual(frappe.get_doc("Purchase Invoice", sheet.purchase_invoice).items[0].qty, 4)
        other = self.make_sheet(length=4)
        other.timesheet_entries[0].start_time = "14:00"
        other.timesheet_entries[0].end_time = "15:30"
        other.insert()
        other.submit()
        self.assertEqual(frappe.get_doc("Purchase Invoice", other.purchase_invoice).items[0].qty, 1.5)
        overlap = self.make_sheet(length=4)
        with self.assertRaisesRegex(frappe.ValidationError, "shift overlaps submitted Timesheet"):
            overlap.insert()

    def test_distinct_worked_hours_include_overnight_and_ignore_idle_dates(self):
        sheet = self.make_sheet(length=4)
        sheet.append("timesheet_entries", {
            "work_date": self.day, "employee": self.employee,
            "start_time": "10:00", "end_time": "14:00",
        })
        sheet.append("timesheet_entries", {
            "work_date": self.day + timedelta(days=2), "employee": self.employee,
            "start_time": "23:00", "end_time": "01:15", "ends_next_day": 1,
        })
        sheet.insert()
        sheet.submit()
        self.assertEqual(sheet.total_operator_hours, 10.25)
        self.assertEqual(sheet.total_crane_billable_hours, 8.25)
        invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
        self.assertEqual(invoice.items[0].qty, 8.25)
        self.assertEqual(invoice.items[0].amount, 8.25 * sheet.purchase_rate)
        from heavy_equipment_rental.billing import generate_sales_invoice
        sale = frappe.get_doc("Sales Invoice", generate_sales_invoice(timesheet=sheet.name)["name"])
        self.assertEqual(sale.items[0].uom, "Hour")
        self.assertEqual(sale.items[0].qty, invoice.items[0].qty)
        self.assertEqual(sale.items[0].rate, 100)

    def test_unchecked_rented_skips_purchase_and_survives_saves(self):
        sheet = self.make_sheet(rate=0)
        sheet.rented = 0
        sheet.insert()
        sheet.save()
        sheet.reload()
        self.assertEqual(sheet.crane_ownership_type, "Rented")
        self.assertEqual(sheet.rented, 0)
        sheet.submit()
        self.assertFalse(sheet.purchase_invoice)
        self.assertIsNone(create_purchase_invoice(sheet))
        from heavy_equipment_rental.billing import generate_sales_invoice
        self.assertTrue(generate_sales_invoice(timesheet=sheet.name)["name"])

    def test_owned_crane_never_creates_purchase_invoice(self):
        self.crane.hired_from_supplier = 0
        self.crane.append("ownership_partners", {"is_company": 1, "ownership_percentage": 100, "profit_percentage": 100})
        self.crane.save()
        sheet = self.make_sheet(rate=0)
        sheet.rented = 1
        sheet.insert()
        self.assertEqual(sheet.rented, 0)
        sheet.submit()
        self.assertFalse(sheet.purchase_invoice)

    def test_worked_hour_migration_preserves_history_and_resets_daily_draft_rate(self):
        from heavy_equipment_rental.patches.use_worked_hour_purchasing import execute

        sheet = self.make_sheet().insert()
        sheet.submit()
        invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
        # Simulate the prior invoice and submitted timesheet snapshot, without reposting GL.
        frappe.db.set_value("Purchase Invoice Item", invoice.items[0].name,
                            {"uom": "Day", "qty": 4, "rate": 80}, update_modified=False)
        frappe.db.set_value("Crane Timesheet", sheet.name,
                            {"rental_rate_unit": "Day", "purchase_rate": 80}, update_modified=False)
        draft = self.make_sheet(offset=1).insert()
        frappe.db.set_value("Crane Timesheet", draft.name,
                            {"rental_rate_unit": "Month", "purchase_rate": 900}, update_modified=False)
        execute()
        sheet.reload()
        draft.reload()
        self.assertEqual(sheet.purchase_rate, 80)
        self.assertEqual(sheet.rented, 1)
        self.assertEqual(draft.purchase_rate, 0)
        self.assertEqual(frappe.parse_json(draft.legacy_purchase_terms)[
            "before_worked_hour_purchasing"]["purchase_rate"], 900)
        archived = sheet.legacy_purchase_terms
        draft.rented = 0
        draft.save()
        execute()
        draft.reload()
        sheet.reload()
        invoice.reload()
        self.assertEqual(draft.rented, 0)
        self.assertEqual(sheet.legacy_purchase_terms, archived)
        self.assertEqual(sheet.purchase_invoice, invoice.name)
        self.assertEqual(invoice.docstatus, 1)
        self.assertEqual(invoice.items[0].uom, "Day")
        self.assertEqual(invoice.items[0].qty, 4)
        self.assertEqual(invoice.items[0].rate, 80)
        sheet.attachment = "/private/files/legacy-hour-purchase-test.pdf"
        sheet.save()
        self.assertEqual(sheet.purchase_rate, 80)
        self.assertEqual(sheet.rental_rate_unit, "Day")

    def test_removed_manual_terms_are_archived_without_repricing(self):
        from heavy_equipment_rental.patches.use_timesheet_purchase_interval import execute

        if not frappe.db.has_column("Crane Timesheet", "purchase_qty"):
            self.skipTest("Legacy purchase columns exist only on upgraded sites")
        sheet = self.make_sheet().insert()
        sheet.submit()
        invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
        frappe.db.set_value("Crane Timesheet", sheet.name, {"purchase_qty": 7, "purchase_rate_unit": "Day"},
                            update_modified=False)
        execute()
        sheet.reload()
        self.assertEqual(frappe.parse_json(sheet.legacy_purchase_terms), {
            "purchase_qty": 7, "purchase_rate_unit": "Day", "purchase_rate": sheet.purchase_rate,
        })
        original_archive = sheet.legacy_purchase_terms
        execute()
        sheet.reload()
        self.assertEqual(sheet.legacy_purchase_terms, original_archive)
        invoice.reload()
        self.assertEqual(invoice.docstatus, 1)
        self.assertEqual(invoice.items[0].uom, "Hour")
        self.assertEqual(invoice.items[0].qty, 4)
        self.assertEqual(sheet.purchase_invoice, invoice.name)
