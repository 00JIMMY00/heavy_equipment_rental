"""Permission-aware native Crane connections, including links in child rows."""

import frappe
from frappe import _


def link_fields():
	"""Include site accounting dimensions and custom links, not just HER fields."""
	fields = frappe.get_all("DocField", filters={"fieldtype": "Link", "options": "Crane"},
		fields=["parent as doctype", "fieldname"])
	fields += frappe.get_all("Custom Field", filters={"fieldtype": "Link", "options": "Crane"},
		fields=["dt as doctype", "fieldname"])
	return fields


def connection_sources():
	sources = {}
	for field in link_fields():
		meta = frappe.get_meta(field.doctype)
		if meta.issingle:
			continue
		if not meta.istable:
			sources.setdefault(meta.name, set()).add((meta.name, field.fieldname))
			continue
		parents = frappe.get_all("DocField", filters={"fieldtype": ["in", ["Table", "Table MultiSelect"]],
			"options": meta.name}, pluck="parent")
		parents += frappe.get_all("Custom Field", filters={"fieldtype": ["in", ["Table", "Table MultiSelect"]],
			"options": meta.name}, pluck="dt")
		for parent in parents:
			parent_meta = frappe.get_meta(parent)
			if not parent_meta.issingle and not parent_meta.istable:
				sources.setdefault(parent, set()).add((meta.name, field.fieldname))
	return sources


def master_links(doc):
	links = {}
	for source in [doc, *[row for field in doc.meta.get_table_fields() for row in doc.get(field.fieldname) or []]]:
		for field in source.meta.fields:
			if field.fieldtype == "Link" and source.get(field.fieldname):
				links.setdefault(field.options, set()).add(source.get(field.fieldname))
	return links


def dashboard_data(sources=None):
	if sources is None:
		sources = connection_sources()
	meta = frappe.get_meta("Crane")
	masters = {f.options for f in meta.fields if f.fieldtype == "Link"}
	for field in meta.get_table_fields():
		masters.update(f.options for f in frappe.get_meta(field.options).fields if f.fieldtype == "Link")
	remaining = set(sources) | masters | {"Asset Depreciation Schedule", "Purchase Receipt", "Purchase Invoice", "Payment Entry"}
	groups = []
	for label, doctypes in (
		("Rental", ["Rental Contract", "Crane Timesheet", "Sales Invoice", "Purchase Invoice"]),
		("Operations", ["Crane Maintenance", "Expense Entry", "Stock Entry", "Asset Repair"]),
		("Profit Sharing & Payments", ["Crane Profit Settlement", "Journal Entry", "Payment Entry"]),
		("Masters", sorted(masters)),
		("Other Linked Documents", sorted(remaining)),
	):
		items = [dt for dt in doctypes if dt in remaining]
		remaining.difference_update(items)
		if items:
			groups.append({"label": _(label), "items": items})
	return {
		"fieldname": "crane",
		"method": "heavy_equipment_rental.crane_connections.get_connections",
		# Scalar links must be strings; lists describe a table and its link field.
		"internal_links": {"Asset": "asset", "Item": "item"},
		"transactions": groups,
	}


def add_accounting_connections(doc, linked):
	"""Follow source vouchers and their payment references, checking each hop."""
	def add(target, filters):
		if not frappe.has_permission(target, "read"):
			return
		linked.setdefault(target, set()).update(frappe.get_list(target, filters=filters,
			pluck="name", distinct=True, limit_page_length=0))

	def follow(source, field, target):
		if not linked.get(source) or not frappe.has_permission(source, "read"):
			return
		values = frappe.get_list(source, filters={"name": ["in", sorted(linked[source])]},
			pluck=field, limit_page_length=0)
		values = sorted({value for value in values if value})
		if values:
			add(target, {"name": ["in", values]})

	for source, field, target in (
		("Asset", "purchase_invoice", "Purchase Invoice"),
		("Asset", "purchase_receipt", "Purchase Receipt"),
		("Crane Timesheet", "sales_invoice", "Sales Invoice"),
		("Crane Timesheet", "purchase_invoice", "Purchase Invoice"),
		("Expense Entry", "journal_entry", "Journal Entry"),
		("Crane Profit Settlement", "journal_entry", "Journal Entry"),
		("Crane Profit Settlement", "sales_invoice", "Sales Invoice"),
	):
		follow(source, field, target)

	# An explicitly selected, non-shared leaf center also attributes purchases
	# (e.g. spare parts) whose native invoice rows have no Crane dimension.
	center = doc.sharing_cost_center
	if center and doc.sharing_company and frappe.has_permission("Cost Center", "read"):
		centers = frappe.get_list("Cost Center", filters={"name": center,
			"company": doc.sharing_company, "is_group": 0}, pluck="name")
		shared = frappe.db.exists("Crane", {"name": ["!=", doc.name], "sharing_cost_center": center})
		if centers and not shared:
			for target, child in (("Sales Invoice", "Sales Invoice Item"),
				("Purchase Invoice", "Purchase Invoice Item"), ("Journal Entry", "Journal Entry Account")):
				add(target, [[target, "company", "=", doc.sharing_company], [child, "cost_center", "=", center]])

	if linked.get("Asset"):
		add("Asset Depreciation Schedule", {"asset": ["in", sorted(linked["Asset"])]})
	if linked.get("Asset Depreciation Schedule"):
		for schedule in sorted(linked["Asset Depreciation Schedule"]):
			values = frappe.get_doc("Asset Depreciation Schedule", schedule)
			values.check_permission("read")
			journals = [row.journal_entry for row in values.depreciation_schedule if row.journal_entry]
			if journals:
				add("Journal Entry", {"name": ["in", journals]})

	if linked.get("Purchase Receipt"):
		add("Purchase Invoice", [["Purchase Invoice Item", "purchase_receipt", "in", sorted(linked["Purchase Receipt"])]])
	for source in ("Sales Invoice", "Purchase Invoice", "Journal Entry"):
		if linked.get(source):
			add("Payment Entry", [["Payment Entry Reference", "reference_doctype", "=", source],
				["Payment Entry Reference", "reference_name", "in", sorted(linked[source])]])


@frappe.whitelist()
def get_connections(doctype, name, items=None):
	if doctype != "Crane":
		frappe.throw(_("Connections are only available for Crane."))
	doc = frappe.get_doc("Crane", name)
	doc.check_permission("read")
	sources = connection_sources()
	masters = master_links(doc)
	allowed = {dt for group in dashboard_data(sources)["transactions"] for dt in group["items"]}
	requested = frappe.parse_json(items) if isinstance(items, str) else items
	requested = allowed if requested is None else allowed.intersection(requested)
	linked = {}
	dependencies = {"Asset", "Crane Timesheet", "Expense Entry", "Crane Profit Settlement",
		"Sales Invoice", "Purchase Invoice", "Journal Entry", "Purchase Receipt"}
	for target in sorted(requested | dependencies):
		if not frappe.has_permission(target, "read"):
			continue
		names = set()
		for source, fieldname in sources.get(target, []):
			names.update(frappe.get_list(target, filters=[[source, fieldname, "=", name]],
				pluck="name", distinct=True, limit_page_length=0))
		if masters.get(target):
			names.update(frappe.get_list(target, filters={"name": ["in", sorted(masters[target])]},
				pluck="name", limit_page_length=0))
		linked[target] = names
	add_accounting_connections(doc, linked)
	# Native dashboard uses these names for both badges and filtered list routes.
	results = [dict(doctype=target, names=sorted(names), count=len(names), open_count=0)
		for target, names in sorted(linked.items()) if target in requested]
	return {"count": {"internal_links_found": results, "external_links_found": []}}
