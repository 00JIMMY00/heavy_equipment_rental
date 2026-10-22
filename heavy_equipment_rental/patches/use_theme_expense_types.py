"""Move rental expenses to the shared Arab ERP expense models."""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Expense Type"):
		return

	old_types = frappe.get_all(
		"Expense Type", fields=["name", "expense_type_name", "account", "description"],
		limit_page_length=0,
	)
	mapping = {}
	for old in old_types:
		company = frappe.db.get_value("Account", old.account, "company")
		if not company:
			frappe.throw(f"Cannot migrate Expense Type {old.name}: its account has no Company")
		new_name = frappe.db.get_value(
			"Expense Entry Type",
			{"title": old.expense_type_name, "company": company, "account": old.account},
			"name",
		)
		if not new_name:
			new_name = frappe.get_doc({
				"doctype": "Expense Entry Type", "title": old.expense_type_name,
				"company": company, "account": old.account, "enabled": 1,
			}).insert(ignore_permissions=True).name
		if old.description:
			from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
			create_custom_fields({"Expense Entry Type": [{
				"fieldname": "rental_legacy_description", "fieldtype": "Small Text",
				"label": "Legacy Description", "insert_after": "account", "read_only": 1,
			}]})
			frappe.db.set_value(
				"Expense Entry Type", new_name, "rental_legacy_description", old.description,
				update_modified=False,
			)
		mapping[old.name] = new_name

	# The old columns survive model sync even though the shared DocType now owns
	# Expense Entry. Populate its child table without resubmitting posted entries.
	if frappe.db.has_column("Expense Entry", "expense_type"):
		rows = frappe.db.sql("""
			SELECT name, expense_type, amount FROM `tabExpense Entry`
			WHERE expense_type IS NOT NULL AND expense_type != ''
		""", as_dict=True)
		for row in rows:
			new_name = mapping.get(row.expense_type)
			if not new_name:
				frappe.throw(f"Cannot migrate Expense Entry {row.name}: missing type {row.expense_type}")
			if not frappe.db.exists("Expense Entry Detail", {"parent": row.name, "parenttype": "Expense Entry"}):
				account = frappe.db.get_value("Expense Entry Type", new_name, "account")
				frappe.get_doc({
					"doctype": "Expense Entry Detail", "parent": row.name,
					"parenttype": "Expense Entry", "parentfield": "expenses", "idx": 1,
					"expense_entry_type": new_name, "expense_entry_account": account,
					"amount": row.amount,
				}).db_insert()
			company = frappe.db.get_value("Expense Entry Type", new_name, "company")
			frappe.db.set_value("Expense Entry", row.name, "company", company, update_modified=False)

	for old_name, new_name in mapping.items():
		frappe.db.sql("""
			UPDATE `tabCrane Maintenance` SET expense_type=%s WHERE expense_type=%s
		""", (new_name, old_name))

	frappe.delete_doc("DocType", "Expense Type", force=True, ignore_permissions=True)
