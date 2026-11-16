"""Refresh saved workspace destinations without replacing user arrangements."""
import frappe


def execute():
    # Native rename retains naming-series Property Setters; update the old default.
    for prop, value in (("default", "RC-.#####"), ("options", "RC-.#####\nASG-.#####")):
        filters = {"doc_type": "Rental Contract", "field_name": "naming_series", "property": prop}
        for name in frappe.get_all("Property Setter", filters=filters, pluck="name"):
            setter = frappe.get_doc("Property Setter", name)
            if setter.value == "ASG-.#####":
                setter.value = value
                setter.save()
    frappe.clear_cache(doctype="Rental Contract")
    replacements = [('Crane Job Assignment', 'Rental Contract'), ('Crane Assignments', 'Rental Contracts'),
                    ('Crane Assignment', 'Rental Contract'), ('crane-assignment', 'rental-contract'),
                    ('تكليف الونش', 'عقد ايجار معدة'), ('تكليف رافعة', 'عقد ايجار معدة')]
    for name in frappe.get_all('Workspace', pluck='name'):
        doc = frappe.get_doc('Workspace', name)
        changed = False
        for field in ('content',):
            value = doc.get(field) or ''
            updated = value
            for old, new in replacements:
                updated = updated.replace(old, new)
            if updated != value:
                doc.set(field, updated)
                changed = True
        for table in ('links', 'shortcuts'):
            for row in doc.get(table) or []:
                for field in ('label', 'link_to'):
                    value = row.get(field) or ''
                    updated = value
                    for old, new in replacements:
                        updated = updated.replace(old, new)
                    if updated != value:
                        row.set(field, updated)
                        changed = True
        if changed:
            doc.save(ignore_permissions=True)
