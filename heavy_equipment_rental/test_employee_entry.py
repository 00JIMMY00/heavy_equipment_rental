"""Employee setup must work with native ERPNext fields on a fresh site."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from heavy_equipment_rental.employee_entry import setup


class TestEmployeeEntry(FrappeTestCase):
    def test_setup_allows_employee_without_birth_date(self):
        frappe.db.savepoint("employee_entry_setup")
        try:
            # Restore the native mandatory, visible birth date to exercise installation.
            frappe.db.delete("Property Setter", {
                "doc_type": "Employee", "field_name": "date_of_birth",
            })
            frappe.clear_cache(doctype="Employee")
            field = frappe.get_meta("Employee").get_field("date_of_birth")
            self.assertTrue(field.reqd)
            self.assertFalse(field.hidden)

            setup()
            setup()  # Migration repeats the same setup on existing sites.
            field = frappe.get_meta("Employee").get_field("date_of_birth")
            self.assertFalse(field.reqd)
            self.assertTrue(field.hidden)

            employee = frappe.get_doc({
                "doctype": "Employee",
                "first_name": "HER optional birth date test",
                "company": frappe.db.get_value("Company", {}, "name"),
                "status": "Active",
                "date_of_joining": today(),
            }).insert()
            self.assertFalse(employee.reload().date_of_birth)
        finally:
            frappe.db.rollback(save_point="employee_entry_setup")
            frappe.clear_cache(doctype="Employee")
