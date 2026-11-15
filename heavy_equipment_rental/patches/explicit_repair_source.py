"""Label historical manual workflows without changing their financial documents."""
import frappe


def execute():
    frappe.db.sql("""UPDATE `tabCrane Maintenance` SET repair_source='Manual Documents'
        WHERE repair_source IS NULL OR repair_source=''""")
