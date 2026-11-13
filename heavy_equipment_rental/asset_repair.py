"""Keep native repair capitalization in sync with actual stock valuation.

Scoped to HER repair jobs; unrelated ERPNext repairs retain native behavior.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from erpnext.assets.doctype.asset_repair.asset_repair import AssetRepair
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions


class RentalAssetRepair(AssetRepair):
	def validate(self):
		if self.get("crane_maintenance"):
			frappe.db.get_value("Asset", self.asset, "name", for_update=True)
		super().validate()

	def before_submit(self):
		book_value = self.asset_doc.value_after_depreciation
		super().before_submit()
		if self.get("crane_maintenance") and not self.asset_doc.calculate_depreciation:
			# Native v15 updates finance-book rows, but omits the manual-depreciation
			# value on the Asset itself. Keep that native value consistent too.
			self.asset_doc.db_set("value_after_depreciation", book_value + self.total_repair_cost)

	def decrease_stock_quantity(self):
		if not self.get("crane_maintenance"):
			return super().decrease_stock_quantity()
		old_value = self.get_total_value_of_stock_consumed()
		entry = frappe.get_doc(dict(doctype="Stock Entry", stock_entry_type="Material Issue",
			company=self.company, asset_repair=self.name, crane=self.crane,
			crane_maintenance=self.crane_maintenance, set_posting_time=1,
			posting_date=getdate(self.completion_date)))
		for row in self.stock_items:
			self.validate_serial_no(row)
			entry.append("items", dict(item_code=row.item_code, s_warehouse=row.warehouse,
				qty=row.consumed_quantity, basic_rate=row.valuation_rate,
				serial_and_batch_bundle=row.serial_and_batch_bundle,
				cost_center=self.cost_center, project=self.project,
				**{field: self.get(field) for field in get_accounting_dimensions()}))
		entry.insert().submit()
		for row, consumed in zip(self.stock_items, entry.items):
			row.total_value = consumed.amount
			row.valuation_rate = flt(consumed.amount) / flt(row.consumed_quantity)
		# Native before_submit already added the estimated stock value. Correct it
		# before native GL creation and depreciation schedule regeneration.
		difference = self.get_total_value_of_stock_consumed() - old_value
		self.asset_doc.total_asset_cost += difference
		self.asset_doc.additional_asset_cost += difference
		if self.asset_doc.calculate_depreciation:
			for book in self.asset_doc.finance_books:
				book.value_after_depreciation += difference
		self.calculate_total_repair_cost()

	def before_cancel(self):
		if not self.get("crane_maintenance"):
			return super().before_cancel()
		# Later repairs must be reversed first: native schedules and asset totals
		# cannot safely be unwound out of order.
		if frappe.db.exists("Asset Repair", {"asset": self.asset, "docstatus": 1,
			"creation": [">", self.creation], "name": ["!=", self.name]}):
			frappe.throw(_("Cancel later Asset Repairs first."))
		self.ignore_linked_doctypes = ("Stock Entry", "GL Entry", "Stock Ledger Entry")
		book_value = frappe.db.get_value("Asset", self.asset, "value_after_depreciation")
		super().before_cancel()
		if not self.asset_doc.calculate_depreciation:
			self.asset_doc.db_set("value_after_depreciation", book_value - self.total_repair_cost)
		self.ignore_linked_doctypes = ("Stock Entry", "GL Entry", "Stock Ledger Entry")

	def on_cancel(self):
		if not self.get("crane_maintenance"):
			return
		for name in frappe.get_all("Stock Entry", filters={"asset_repair": self.name, "docstatus": 1}, pluck="name"):
			frappe.get_doc("Stock Entry", name).cancel()
		super().cancel_sabb()

	def cancel_sabb(self):
		# Stock Entry restores bundle ownership to Asset Repair on cancellation.
		# Wait for that native step before cancelling the repair's bundles.
		if not self.get("crane_maintenance"):
			return super().cancel_sabb()
