import frappe


def execute():
    # Preserve owner rows and dated agreements; supplier hire determines current classification.
    frappe.db.sql("""UPDATE `tabCrane` SET ownership_classification='Hired from Supplier',
        ownership_type='Rented' WHERE hired_from_supplier=1""")
