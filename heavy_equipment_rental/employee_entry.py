"""Minimal employee creation using native defaults and validation."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup():
    create_custom_fields({"Employee": [
        dict(fieldname="her_salary_column", fieldtype="Column Break", insert_after="salary_mode"),
        dict(fieldname="her_basic_salary", fieldtype="Currency", label="Basic Salary",
             insert_after="her_salary_column", non_negative=1, options="Company:company:default_currency"),
        dict(fieldname="her_kpi_incentive", fieldtype="Currency", label="KPI Incentive",
             insert_after="her_basic_salary", non_negative=1, options="Company:company:default_currency"),
    ]})
    for field, prop, value, kind in (
        ('gender', 'default', 'Male', 'Data'),
        ('gender', 'hidden', '1', 'Check'),
        ('salutation', 'hidden', '1', 'Check'),
        # Frappe validates each setter: make the native required field optional first.
        ('date_of_birth', 'reqd', '0', 'Check'),
        ('date_of_birth', 'hidden', '1', 'Check'),
        ('date_of_joining', 'default', 'Today', 'Data'),
    ):
        frappe.make_property_setter({'doctype': 'Employee', 'fieldname': field,
            'property': prop, 'value': value, 'property_type': kind}, module='Heavy Equipment Rental')
    frappe.make_property_setter({'doctype': 'Employee', 'doctype_or_field': 'DocType',
        'property': 'quick_entry', 'value': '1', 'property_type': 'Check'}, module='Heavy Equipment Rental')

    frappe.make_property_setter({'doctype': 'Employee', 'doctype_or_field': 'DocType',
        'property': 'show_title_field_in_link', 'value': '1', 'property_type': 'Check'}, module='Heavy Equipment Rental')
