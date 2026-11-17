"""Current shares apply without date gates; posted evidence remains immutable."""
import json
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days

from heavy_equipment_rental.profit_sharing import agreement_for


class TestStaticCraneShares(FrappeTestCase):
    def setUp(self):
        from heavy_equipment_rental.test_consolidated_expenses import TestGroupedExpenses
        self.fixture = TestGroupedExpenses()
        self.fixture.setUp()
        f = self.fixture
        owner = frappe.get_doc(dict(doctype='Shareholder', title='Static owner '+frappe.generate_hash(length=8), company=f.company)).insert()
        f.crane.update(dict(enable_profit_sharing=1, sharing_company=f.company, ownership_type='Shared Ownership'))
        f.crane.set('ownership_partners', [dict(is_company=1, ownership_percentage=50, profit_percentage=50),
            dict(shareholder=owner.name, ownership_percentage=50, profit_percentage=50)])
        f.crane.save()

    def set_shares(self, company_share):
        crane = self.fixture.crane
        for row in crane.ownership_partners:
            row.ownership_percentage = row.profit_percentage = company_share if row.is_company else 100-company_share
        crane.save()
        return crane

    def test_same_day_changes_apply_to_any_work_date_and_asset_ownership(self):
        from heavy_equipment_rental.crane_assets import company_ownership_percentage
        self.assertFalse(frappe.get_meta('Crane').has_field('agreement_effective_from'))
        for share in (60, 70, 35):
            crane = self.set_shares(share)
            for start, end in [('2020-01-01', '2020-02-01'), ('2030-01-01', '2030-12-31')]:
                agreement = agreement_for(crane, start, end)
                self.assertEqual(next(r['profit_percentage'] for r in agreement['partners'] if r['is_company']), share)
                self.assertNotIn('effective_from', agreement)
            self.assertEqual(company_ownership_percentage(crane), share)
        crane.enable_profit_sharing = 0
        crane.save()
        with self.assertRaises(frappe.ValidationError):
            agreement_for(crane, today(), today())
        crane.enable_profit_sharing = 1
        crane.save()
        self.assertTrue(agreement_for(crane)['enabled'])

    def test_draft_recalculates_but_submitted_settlement_and_journal_are_preserved(self):
        from heavy_equipment_rental.timesheet_settlement import ensure_settlement
        from heavy_equipment_rental.billing import generate_sales_invoice
        f = self.fixture
        settlement = ensure_settlement(f.sheet)
        self.set_shares(60)
        settlement.save()
        self.assertEqual(next(r.profit_percentage for r in settlement.shares if r.is_company), 60)
        invoice = frappe.get_doc('Sales Invoice', generate_sales_invoice(timesheet=f.sheet.name)['name'])
        invoice.submit()
        settlement.reload()
        self.assertEqual(settlement.docstatus, 1)
        snapshot = (settlement.agreement_snapshot, settlement.source_snapshot, [row.as_dict() for row in settlement.shares])
        journal = frappe.get_doc('Journal Entry', settlement.journal_entry).as_dict()
        self.set_shares(80)
        self.assertEqual((settlement.reload().agreement_snapshot, settlement.source_snapshot, [row.as_dict() for row in settlement.shares]), snapshot)
        self.assertEqual(frappe.get_doc('Journal Entry', settlement.journal_entry).as_dict(), journal)
        self.assertEqual(next(r['profit_percentage'] for r in agreement_for(f.crane)['partners'] if r['is_company']), 80)

    def test_archive_patch_is_repeatable_and_does_not_change_ledger(self):
        from heavy_equipment_rental.patches.archive_dated_crane_agreements import execute
        crane = self.fixture.crane
        before = crane.agreement_history
        frappe.db.set_value('Crane', crane.name, 'agreement_effective_from', '2035-01-01', update_modified=False)
        modified = crane.modified
        execute()
        archive = crane.reload().legacy_agreement_data
        self.assertEqual(json.loads(archive)['agreement_effective_from'], '2035-01-01')
        execute()
        self.assertEqual(crane.reload().legacy_agreement_data, archive)
        self.assertEqual(str(crane.modified), str(modified))
        self.assertEqual(crane.agreement_history, before)
