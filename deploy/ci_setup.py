"""Disposable CI fixtures. This file is never executed by installation/migration."""
import frappe
from frappe.utils import now_datetime
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

assert frappe.local.site == 'her_ci', 'Fixtures are restricted to the disposable CI site'
year = now_datetime().year
setup_complete(dict(currency='EGP', full_name='HER CI', company_name='cranes company',
    timezone='Africa/Cairo', company_abbr='CC', industry='Manufacturing', country='Egypt',
    fy_start_date=f'{year}-01-01', fy_end_date=f'{year}-12-31', language='english',
    email='ci@example.invalid', password='ci-only-password', chart_of_accounts='Standard'))
frappe.db.set_value('Company', 'cranes company', 'enable_perpetual_inventory', 1)
frappe.defaults.set_global_default('company', 'cranes company')
if not frappe.db.exists('Company', 'Other CI Company'):
    frappe.get_doc(dict(doctype='Company', company_name='Other CI Company', abbr='OCC',
        default_currency='EGP', country='Egypt', chart_of_accounts='Standard')).insert()
from heavy_equipment_rental.demo import create_rental_cycle
create_rental_cycle('cranes company')
frappe.db.commit()
