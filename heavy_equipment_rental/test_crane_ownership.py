import json
import frappe
from frappe.tests.utils import FrappeTestCase


class TestCraneOwnership(FrappeTestCase):
    def test_owned_and_hired_are_independent(self):
        crane = frappe.get_doc(dict(doctype='Crane', crane_name='Ownership test')).insert()
        self.assertEqual(crane.ownership_classification, 'Company Owned')
        self.assertEqual(crane.ownership_partners[0].ownership_percentage,100)
        supplier=frappe.db.get_value('Supplier',{},'name')
        self.assertTrue(supplier)
        crane.hired_from_supplier=1
        crane.supplier=supplier
        crane.set('ownership_partners',[])
        crane.save()
        self.assertEqual(crane.ownership_classification,'Ownership Not Recorded')
        crane.hired_from_supplier=0
        with self.assertRaises(frappe.ValidationError): crane.save()

    def test_migration_preserves_agreements(self):
        from heavy_equipment_rental.patches.simplify_crane_ownership import execute
        before=frappe.get_all('Crane',fields=['name','agreement_history','modified','ownership_type'])
        execute(); execute()
        self.assertEqual(before,frappe.get_all('Crane',fields=['name','agreement_history','modified','ownership_type']))

    def test_company_can_receive_all_profit_and_pay_external_operator(self):
        from heavy_equipment_rental import demo
        from unittest.mock import patch
        from heavy_equipment_rental.test_partner_settlements import TestPartnerSettlements
        company=frappe.db.get_value('Company',{},'name')
        original=demo.create_rental_cycle
        def cycle(name,*args,**kwargs): return original(company,*args,**kwargs)
        fixture=TestPartnerSettlements()
        with patch.object(demo,'create_rental_cycle',side_effect=cycle): fixture.setUp()
        crane=fixture.crane
        crane.enable_profit_sharing=1
        crane.set('ownership_partners',[dict(is_company=1,ownership_percentage=100,profit_percentage=100)])
        crane.operator_type='External Operator'
        crane.operating_shareholder=fixture.partners[0].name
        crane.operating_percentage=10
        crane.set("operating_fees", [dict(is_company=0,shareholder=fixture.partners[0].name,basis="Grand Total",percentage=10)])
        crane.save()
        sheet=fixture.sheet()
        fixture.invoice(sheet).submit()
        settlement=frappe.get_doc('Crane Profit Settlement',sheet.profit_settlement)
        self.assertEqual(settlement.external_distribution,800)
        self.assertEqual(settlement.company_retained,7200)
        self.assertEqual(next(r.shareholder for r in settlement.shares if not r.is_company),fixture.partners[0].name)

    def test_supplier_hire_and_profit_sharing_are_mutually_exclusive(self):
        crane=frappe.get_doc(dict(doctype='Crane',crane_name='Exclusive crane options')).insert()
        crane.enable_profit_sharing=1
        crane.hired_from_supplier=1
        with self.assertRaisesRegex(frappe.ValidationError, 'not both'):
            crane.save()
        crane.reload()
        crane.hired_from_supplier=1
        crane.supplier=frappe.db.get_value('Supplier',{},'name')
        crane.save()
        self.assertFalse(crane.enable_profit_sharing)
        self.assertTrue(crane.hired_from_supplier)
