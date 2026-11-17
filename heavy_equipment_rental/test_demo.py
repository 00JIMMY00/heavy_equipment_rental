"""Independent demo cycles must coexist with legacy demo Crane IDs."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from heavy_equipment_rental import demo


class TestDemo(FrappeTestCase):
    def test_distinct_cycles_keep_unique_cranes_and_repeat_without_duplicates(self):
        frappe.db.savepoint("demo_crane_ids")
        try:
            company = frappe.db.get_value("Company", {}, "name")
            if not frappe.db.exists("Crane", "HER-DEMO-50"):
                frappe.get_doc(dict(doctype="Crane", crane_id="HER-DEMO-50",
                    crane_name="Legacy demo crane")).insert()
            legacy = frappe.get_doc("Crane", "HER-DEMO-50").as_dict()
            cycles = []
            for _ in range(2):
                location = "HER demo isolation " + frappe.generate_hash(length=12)
                with patch.object(demo, "DEMO_LOCATION", location):
                    cycle = demo.create_rental_cycle(company)
                    count = frappe.db.count("Crane")
                    repeated = demo.create_rental_cycle(company)
                    self.assertEqual(repeated["assignment"], cycle["assignment"])
                    self.assertEqual(repeated["crane"], cycle["crane"])
                    self.assertEqual(frappe.db.count("Crane"), count)
                    self.assertEqual(frappe.db.count("Rental Contract", {
                        "company": company, "location": location,
                    }), 1)
                cycles.append(cycle)
            self.assertEqual(len({cycle["crane"] for cycle in cycles}), 2)
            for cycle in cycles:
                self.assertNotEqual(cycle["crane"], legacy.name)
                crane = frappe.get_doc("Crane", cycle["crane"])
                self.assertEqual(crane.crane_id, crane.name)
            self.assertEqual(frappe.get_doc("Crane", legacy.name).as_dict(), legacy)
        finally:
            frappe.db.rollback(save_point="demo_crane_ids")
