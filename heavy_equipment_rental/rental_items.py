"""Rental services are reusable products; a physical crane is a separate Asset."""

from contextlib import contextmanager

import frappe
from frappe import _


def validate_service_item(name):
	item = frappe.get_doc("Item", name)
	if (item.disabled or item.is_stock_item or item.is_fixed_asset or not item.is_sales_item
		or not item.is_purchase_item or item.stock_uom != "Hour"):
		frappe.throw(_("Rental Service Item must be enabled, non-stock, non-fixed-asset, purchasable and sellable, with Hour UOM."))
	return item


def default_service_item():
	name = frappe.db.get_single_value("Heavy Equipment Rental Settings", "rental_service_item")
	if not name:
		name = "HER-RENTAL-SERVICE"
		if not frappe.db.exists("Item", name):
			frappe.get_doc(dict(doctype="Item", item_code=name, item_name=_("Crane Rental Service"),
				item_group="Services" if frappe.db.exists("Item Group", "Services") else
				frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				stock_uom="Hour", is_stock_item=0, is_fixed_asset=0,
				is_sales_item=1, is_purchase_item=1)).insert(ignore_permissions=True)
		frappe.db.set_single_value("Heavy Equipment Rental Settings", "rental_service_item", name)
	validate_service_item(name)
	return name


@contextmanager
def preserve_rental_income_defaults():
	"""Demo-specific invoice accounts must not become shared Item defaults.

	ERPNext's SellingController learns a non-company income account when an
	Item's company default is empty, even when merely saving a draft invoice.
	"""
	item = default_service_item()
	before = {r.company: r.income_account for r in frappe.get_all("Item Default",
		filters={"parent": item, "parenttype": "Item"}, fields=["company", "income_account"])}
	try:
		yield
	finally:
		for row in frappe.get_all("Item Default", filters={"parent": item, "parenttype": "Item"},
			fields=["name", "company", "income_account"]):
			original = before.get(row.company)
			if row.income_account != original:
				frappe.db.set_value("Item Default", row.name, "income_account", original, update_modified=False)
		frappe.clear_document_cache("Item", item)
