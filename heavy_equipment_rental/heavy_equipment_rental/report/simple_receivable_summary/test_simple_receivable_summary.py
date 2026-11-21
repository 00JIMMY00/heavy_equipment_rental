import frappe
from erpnext import get_default_company
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from heavy_equipment_rental.rental_items import default_service_item
from heavy_equipment_rental.receivable_payments import make_payment_entry

from .simple_receivable_summary import execute


class TestSimpleReceivableSummary(FrappeTestCase):
    def setUp(self):
        self.company = frappe.get_doc("Company", get_default_company())
        self.customer = self.make_customer()
        self.posting_date = add_days(today(), -5)
        self.historical_date = add_days(today(), -2)

    def tearDown(self):
        frappe.db.rollback()

    def make_customer(self):
        return frappe.get_doc(dict(
            doctype="Customer", customer_name=f"Receivable test {frappe.generate_hash(length=8)}",
            customer_type="Company",
            customer_group=frappe.db.get_value("Customer Group", {"is_group": 0}),
            territory=frappe.db.get_value("Territory", {"is_group": 0}),
        )).insert().name

    def invoice(self, amount, *, customer=None, due_date=None):
        invoice = frappe.get_doc(dict(
            doctype="Sales Invoice", company=self.company.name, customer=customer or self.customer,
            set_posting_time=1, posting_date=self.posting_date, due_date=due_date or self.posting_date,
            currency=self.company.default_currency, conversion_rate=1,
            items=[dict(item_code=default_service_item(), qty=1, rate=amount, uom="Hour",
                        income_account=self.company.default_income_account, cost_center=self.company.cost_center)],
        ))
        invoice.set_missing_values()
        invoice.set("taxes", [])
        return invoice.insert().submit()

    def test_historical_balances_and_receipt_use_different_dates(self):
        first = self.invoice(100)
        second = self.invoice(75, due_date=add_days(today(), 2))
        paid = make_payment_entry([first.name])
        paid.paid_amount = paid.received_amount = paid.references[0].allocated_amount = 40
        paid.reference_no, paid.reference_date = "HER receivable test", today()
        paid.insert().submit()

        filters = dict(company=self.company.name, customer=self.customer)
        _, grouped, _, chart, summary, _ = execute(dict(filters, report_date=self.historical_date))
        self.assertEqual([row.indent for row in grouped], [0, 1, 1])
        self.assertEqual(grouped[0].invoice_names, [first.name, second.name])
        self.assertEqual([entry["value"] for entry in summary], [175, 0, 175, 100, 2])
        self.assertEqual(chart["data"]["datasets"][0]["values"], [175])

        _, overdue, _, _, summary, _ = execute(dict(filters, group_by="Invoice", overdue_only=1))
        self.assertEqual([row.invoice for row in overdue], [first.name])
        self.assertEqual([entry["value"] for entry in summary], [100, 40, 60, 60, 1])

        combined = make_payment_entry([first.name, second.name, first.name])
        self.assertTrue(combined.is_new())
        self.assertEqual(combined.payment_type, "Receive")
        self.assertEqual(combined.paid_amount, 135)
        self.assertEqual({row.reference_name: row.allocated_amount for row in combined.references}, {
            first.name: 60, second.name: 75,
        })

    def test_combined_receipt_rejects_mixed_customers_and_closed_invoices(self):
        first = self.invoice(100)
        second = self.invoice(50, customer=self.make_customer())
        with self.assertRaisesRegex(frappe.ValidationError, "same customer"):
            make_payment_entry([first.name, second.name])

        paid = make_payment_entry([first.name])
        paid.reference_no, paid.reference_date = "HER receivable test", today()
        paid.insert().submit()
        with self.assertRaisesRegex(frappe.ValidationError, "no longer payable"):
            make_payment_entry([first.name])
