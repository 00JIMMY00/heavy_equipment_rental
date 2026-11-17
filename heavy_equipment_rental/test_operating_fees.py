import json
from unittest.mock import patch
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days


class TestOperatingFees(FrappeTestCase):
    def setup_cycle(self):
        from heavy_equipment_rental import demo
        from heavy_equipment_rental.test_partner_settlements import TestPartnerSettlements
        original=demo.create_rental_cycle
        company=frappe.db.get_value('Company',{},'name')
        fixture=TestPartnerSettlements()
        with patch.object(demo,'create_rental_cycle',side_effect=lambda name,*a,**k:original(company,*a,**k)):
            fixture.setUp()
        return fixture

    def test_mixed_bases_post_to_recipients_and_protect_history(self):
        f=self.setup_cycle()
        crane=f.crane
        crane.enable_profit_sharing=1
        crane.set('operating_fees',[dict(is_company=1,basis='Grand Total',percentage=10),
            dict(is_company=0,shareholder=f.partners[0].name,basis='Net Profit',percentage=10)])
        crane.save()
        f.rental_expense(2000).insert().submit()
        sheet=f.sheet()
        f.invoice(sheet).submit()
        settlement=frappe.get_doc('Crane Profit Settlement',sheet.profit_settlement)
        self.assertEqual((settlement.revenue,settlement.operating_expenses,settlement.operating_fee),(8000,2000,1400))
        self.assertEqual((settlement.company_retained,settlement.external_distribution),(3100,2900))
        fees=json.loads(settlement.agreement_snapshot)['operating_fee_breakdown']
        self.assertEqual(sorted(r['amount'] for r in fees),[600,800])
        self.assertEqual(frappe.db.get_value('Journal Entry',settlement.journal_entry,'docstatus'),1)
        snapshot=settlement.agreement_snapshot
        crane.operating_fees[0].percentage=20
        crane.save()
        self.assertEqual(settlement.reload().agreement_snapshot,snapshot)

    def test_defaults_and_validation(self):
        crane=frappe.get_doc(dict(doctype='Crane',crane_id=frappe.generate_hash(length=12),crane_name='Default operating fees')).insert()
        row=crane.operating_fees[0]
        self.assertEqual((row.is_company,row.basis,row.percentage),(1,'Grand Total',0))
        row.percentage=1
        with self.assertRaisesRegex(frappe.ValidationError,'Enable Profit Sharing'):
            crane.save()
        crane.reload()
        row=crane.operating_fees[0]
        row.percentage=-1
        with self.assertRaises(frappe.ValidationError): crane.save()
        crane.reload()
        crane.append('operating_fees',dict(is_company=1,basis='Grand Total',percentage=0))
        with self.assertRaisesRegex(frappe.ValidationError,'once per fee basis'): crane.save()

    def test_legacy_calculation_and_migration(self):
        from heavy_equipment_rental.operating_fees import calculate
        from heavy_equipment_rental.patches.crane_operating_fees import execute
        self.assertEqual(calculate(dict(operator_type='Our Company',operating_percentage=10),8000,2000,2)[0]['amount'],800)
        self.assertEqual(calculate(dict(operating_fees=[dict(is_company=1,basis='Net Profit',percentage=10)]),100,200,2)[0]['amount'],0)
        fields=['name','modified','agreement_history']
        before=frappe.get_all('Crane',fields=fields,order_by='name')
        count=frappe.db.count('Crane Operating Fee')
        execute();execute()
        self.assertEqual(before,frappe.get_all('Crane',fields=fields,order_by='name'))
        self.assertEqual(count,frappe.db.count('Crane Operating Fee'))
