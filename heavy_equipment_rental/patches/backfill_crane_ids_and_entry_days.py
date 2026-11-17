import frappe


def execute():
    frappe.db.sql("UPDATE `tabCrane` SET crane_id = name WHERE COALESCE(crane_id, '') = ''")
    frappe.db.sql("""
        UPDATE `tabTimesheet Entry`
        SET day_name = ELT(WEEKDAY(work_date) + 1, 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
        WHERE work_date IS NOT NULL AND COALESCE(day_name, '') = ''
    """)
