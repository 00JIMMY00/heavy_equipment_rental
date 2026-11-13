"""Link physical cranes to native assets without posting or duplicating accounting."""

import json
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from heavy_equipment_rental.profit_sharing import allocate_amount


def validate_asset_link(crane):
	crane.asset = crane.asset or None
	before = crane.get_doc_before_save()
	previous = before.asset if before else None
	if crane.asset != previous:
		frappe.only_for(("Accounts Manager", "System Manager"))
	if not crane.asset:
		return
	# Serialize against other Crane links and Asset edits; the unique column is
	# the final protection against concurrent inserts.
	frappe.db.get_value("Asset", crane.asset, "name", for_update=True)
	asset = frappe.get_doc("Asset", crane.asset)
	if crane.asset != previous:
		asset.check_permission("read")
		if asset.docstatus == 2 or asset.status in ("Sold", "Scrapped", "Capitalized"):
			frappe.throw(_("Select a draft or active Asset that has not been disposed of."))
	validate_pair(crane, asset)
	if frappe.db.exists("Crane", {"asset": asset.name, "name": ["!=", crane.name]}):
		frappe.throw(_("This Asset is already linked to another Crane."))


def validate_pair(crane, asset):
	if crane.sharing_company and asset.company != crane.sharing_company:
		frappe.throw(_("The Asset Company must match the Crane Agreement Company."))
	if flt(asset.asset_quantity) != 1:
		frappe.throw(_("A Crane must link to an Asset with quantity 1. Split grouped assets using ERPNext first."))
	if asset.item_code == crane.item:
		frappe.throw(_("The fixed-asset Item must be separate from the Crane rental service Item."))
	company_owned = asset.asset_owner == "Company" and (asset.asset_owner_company or asset.company) == asset.company
	if crane.ownership_type in ("Rented", "Operated for Owner"):
		if company_owned:
			frappe.throw(_("Rented and Operated for Owner cranes require a third-party-owned Asset; do not capitalize them as company-owned assets."))
		if not ((asset.asset_owner == "Supplier" and asset.supplier)
			or (asset.asset_owner == "Customer" and asset.customer)
			or (asset.asset_owner == "Company" and asset.asset_owner_company)):
			frappe.throw(_("Identify the third-party owner on the Asset before linking it to this Crane."))
		if crane.ownership_type == "Rented" and asset.asset_owner == "Supplier" and asset.supplier != crane.supplier:
			frappe.throw(_("The Asset owner Supplier must match the rented Crane Supplier."))
	elif not company_owned:
		frappe.throw(_("Owned and shared cranes require an Asset owned by its accounting Company."))


def validate_linked_asset(asset, method=None):
	"""Apply the same checks when native Asset master data changes."""
	if asset.is_new():
		return
	frappe.db.get_value("Asset", asset.name, "name", for_update=True)
	for name in frappe.get_all("Crane", filters={"asset": asset.name}, pluck="name"):
		validate_pair(frappe.get_doc("Crane", name), asset)


def ownership_as_of(crane, date):
	versions = [v for v in json.loads(crane.agreement_history or "[]")
		if getdate(v["effective_from"]) <= getdate(date)]
	if versions:
		version = versions[-1]
		if version["enabled"]:
			return version["partners"]
		ownership_type = version["ownership_type"]
	else:
		ownership_type = crane.ownership_type if not crane.agreement_history else None
	if ownership_type == "Owned":
		return [dict(is_company=1, ownership_percentage=100)]
	return []


@frappe.whitelist()
def asset_summary(crane):
	"""Read live values, never cache financial amounts on the operational master."""
	crane = frappe.get_doc("Crane", crane)
	crane.check_permission("read")
	if not crane.asset:
		return None
	asset = frappe.get_doc("Asset", crane.asset)
	asset.check_permission("read")
	currency = frappe.get_cached_value("Company", asset.company, "default_currency")
	finance_book = frappe.get_cached_value("Company", asset.company, "default_finance_book")
	if not finance_book and len(asset.finance_books) == 1:
		finance_book = asset.finance_books[0].finance_book
	# Do not silently select another finance book if the default is missing.
	if asset.calculate_depreciation and not finance_book and len(asset.finance_books) != 1:
		book_value = None
	else:
		book_value = asset.get_value_after_depreciation(finance_book)
	precision = frappe.get_precision("Asset", "gross_purchase_amount", currency=currency)
	owners = ownership_as_of(crane, today())
	if sum(Decimal(str(p["ownership_percentage"])) for p in owners) != 100:
		owners = []
	weights = [p["ownership_percentage"] for p in owners]
	costs = allocate_amount(asset.gross_purchase_amount, weights, precision) if owners else []
	values = allocate_amount(book_value, weights, precision) if owners and book_value is not None else [None] * len(owners)
	shares = []
	for owner, cost, value in zip(owners, costs, values):
		identity = asset.company if owner["is_company"] else owner.get("shareholder") or owner.get("supplier")
		label = identity
		if not owner["is_company"] and identity:
			party_type, title_field = ("Shareholder", "title") if owner.get("shareholder") else ("Supplier", "supplier_name")
			if frappe.has_permission(party_type, "read", doc=identity):
				label = frappe.db.get_value(party_type, identity, title_field) or identity
		shares.append(dict(owner=identity, owner_label=label,
			ownership_percentage=owner["ownership_percentage"], cost=cost, book_value=value))
	return dict(asset=asset.name, company=asset.company, currency=currency, status=asset.status,
		docstatus=asset.docstatus, asset_owner=asset.asset_owner, finance_book=finance_book,
		gross_purchase_amount=asset.gross_purchase_amount, book_value=book_value,
		as_of=today(), shares=shares)
