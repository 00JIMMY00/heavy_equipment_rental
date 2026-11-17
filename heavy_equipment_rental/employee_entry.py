"""Minimal employee creation using native defaults and validation."""
import frappe


def setup():
    for field, prop, value, kind in (
        ('gender', 'default', 'Male', 'Data'),
        ('gender', 'hidden', '1', 'Check'),
        ('salutation', 'hidden', '1', 'Check'),
        ('date_of_birth', 'hidden', '1', 'Check'),
        ('date_of_birth', 'reqd', '0', 'Check'),
        ('date_of_joining', 'default', 'Today', 'Data'),
    ):
        frappe.make_property_setter({'doctype': 'Employee', 'fieldname': field,
            'property': prop, 'value': value, 'property_type': kind}, module='Heavy Equipment Rental')
    frappe.make_property_setter({'doctype': 'Employee', 'doctype_or_field': 'DocType',
        'property': 'quick_entry', 'value': '1', 'property_type': 'Check'}, module='Heavy Equipment Rental')

    frappe.make_property_setter({'doctype': 'Employee', 'doctype_or_field': 'DocType',
        'property': 'show_title_field_in_link', 'value': '1', 'property_type': 'Check'}, module='Heavy Equipment Rental')
