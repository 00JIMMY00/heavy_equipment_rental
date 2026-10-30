"""Rented crane purchasing uses native ERPNext invoices and payments."""

from datetime import timedelta

import erpnext
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from heavy_equipment_rental.purchasing import (
    create_purchase_invoice,
    make_supplier_payment,
    supplier_payment_invoices,
)


class TestCraneTimesheet(FrappeTestCase):
    def setUp(self):
        self.key = frappe.generate_hash(length=8)
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
            "ownership_type": "Rented", "supplier": self.supplier.name,
            "operational_condition": "Operational",
        }).insert()
        self.day = getdate(today()) - timedelta(days=30)
        self.assignment = frappe.get_doc({
            "doctype": "Crane Assignment", "company": self.company,
            "customer": self.customer.name, "location": "Supplier test yard " + self.key,
            "assigned_cranes": [{
                "crane": self.crane.name, "start_date": self.day,
                "expected_end_date": self.day + timedelta(days=10),
                "rental_rate_unit": "Hour", "rental_rate": 100,
            }],
        }).insert()

    def make_sheet(self, offset=0, unit="Hour", qty=4, rate=25):
        day = self.day + timedelta(days=offset)
        return frappe.get_doc({
            "doctype": "Crane Timesheet", "assignment": self.assignment.name,
            "crane": self.crane.name, "period_start": day, "period_end": day,
            "purchase_rate_unit": unit, "purchase_qty": qty, "purchase_rate": rate,
            "driver": self.employee,
            "timesheet_entries": [{"work_date": day, "start_time": "08:00", "end_time": "12:00"}],
        })

    def test_invoice_posting_units_payments_and_cancellation(self):
        for offset, (unit, qty, rate) in enumerate((("Hour", 4, 25), ("Day", 2, 80), ("Month", 0.5, 900))):
            sheet = self.make_sheet(offset, unit, qty, rate).insert()
            self.assertFalse(sheet.purchase_invoice)
            self.assertEqual(sheet.purchase_supplier, self.supplier.name)
            sheet.submit()
            invoice = frappe.get_doc("Purchase Invoice", sheet.purchase_invoice)
            self.assertEqual(invoice.docstatus, 1)
            self.assertEqual(invoice.supplier, self.supplier.name)
            self.assertEqual(invoice.company, self.company)
            self.assertEqual(invoice.currency, frappe.get_cached_value("Company", self.company, "default_currency"))
            self.assertEqual(invoice.items[0].item_code, self.crane.item)
            self.assertAlmostEqual(invoice.items[0].amount, qty * rate)
            self.assertIn(unit, invoice.items[0].description)
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
        for values in ({"purchase_qty": 0}, {"purchase_rate": -1}, {"purchase_rate_unit": "Year"},
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
