"""Link physical cranes to native assets without posting or duplicating accounting."""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, today



def company_ownership_percentage(crane):
	if crane.ownership_type == "Owned":
		return 100.0
	if crane.ownership_type in ("Rented", "Operated for Owner"):
		return 0.0
	owners = ownership_as_of(crane, today()) if crane.agreement_history else crane.ownership_partners
	return sum(flt(row.get("ownership_percentage")) for row in owners if row.get("is_company"))


def accounting_basis(crane):
	if not company_ownership_percentage(crane):
		return ""
	return "Company Owned" if crane.ownership_type == "Owned" else "Company Interest Only"


def validate_asset_link(crane):
	crane.asset = crane.asset or None
	before = crane.get_doc_before_save()
	previous = before.asset if before else None
	crane.asset_accounting_basis = accounting_basis(crane)
	if crane.asset != previous:
		frappe.only_for(("Accounts Manager", "System Manager"))
	if not crane.asset:
		return
	if not crane.asset_accounting_basis:
		frappe.throw(_("Only cranes with a positive Company ownership percentage can link an Asset. Clear the Asset link; its accounting history remains intact."))
	frappe.db.get_value("Asset", crane.asset, "name", for_update=True)
	asset = frappe.get_doc("Asset", crane.asset)
	if crane.asset != previous:
		asset.check_permission("read")
		if asset.docstatus == 2 or asset.status in ("Sold", "Scrapped", "Capitalized"):
			frappe.throw(_("Select a draft or active Asset that has not been disposed of."))
	if not crane.sharing_company:
		crane.sharing_company = asset.company
	validate_pair(crane, asset)
	if frappe.db.exists("Crane", {"asset": asset.name, "name": ["!=", crane.name]}):
		frappe.throw(_("This Asset is already linked to another Crane."))


def validate_pair(crane, asset):
	if not company_ownership_percentage(crane):
		frappe.throw(_("Only cranes with a positive Company ownership percentage can link an Asset."))
	if crane.sharing_company and asset.company != crane.sharing_company:
		frappe.throw(_("The Asset Company must match the Crane Agreement Company."))
	if flt(asset.asset_quantity) != 1:
		frappe.throw(_("A Crane must link to an Asset with quantity 1. Split grouped assets using ERPNext first."))
	if asset.item_code == crane.item:
		frappe.throw(_("The fixed-asset Item must be separate from the Crane rental service Item."))
	if asset.asset_owner != "Company" or (asset.asset_owner_company or asset.company) != asset.company:
		frappe.throw(_("The Asset must represent this Company's owned interest."))


@frappe.whitelist()
def make_company_asset(crane):
	crane = frappe.get_doc("Crane", crane)
	crane.check_permission("read")
	frappe.has_permission("Asset", "create", throw=True)
	if not accounting_basis(crane):
		frappe.throw(_("This Company owns no percentage of this Crane; no Asset can be created from it."))
	if crane.asset:
		frappe.throw(_("This Crane already has an Asset."))
	asset = frappe.new_doc("Asset")
	asset.update(dict(asset_name=(crane.crane_name if crane.ownership_type == "Owned" else
		_("{0} - Company {1}% interest").format(crane.crane_name, company_ownership_percentage(crane))), company=crane.sharing_company,
		asset_owner="Company", asset_owner_company=crane.sharing_company, asset_quantity=1))
	return asset.as_dict()


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
	if not crane.asset or not company_ownership_percentage(crane):
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
	return dict(asset=asset.name, company=asset.company, currency=currency, status=asset.status,
		docstatus=asset.docstatus, asset_owner=asset.asset_owner, finance_book=finance_book,
		gross_purchase_amount=asset.gross_purchase_amount, total_asset_cost=asset.total_asset_cost,
		additional_asset_cost=asset.additional_asset_cost, recognition_basis=accounting_basis(crane), book_value=book_value,
		as_of=today(), company_ownership_percentage=company_ownership_percentage(crane), shares=[])
