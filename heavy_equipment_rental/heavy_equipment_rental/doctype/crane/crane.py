import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import set_new_name

from heavy_equipment_rental.rental_validation import check_non_negative, lock_cranes
from heavy_equipment_rental.item_prices import sync_crane_item_prices


class Crane(Document):
	def after_insert(self):
		self.ensure_sales_item()
		sync_crane_item_prices(self)

	def on_update(self):
		self.ensure_sales_item()
		sync_crane_item_prices(self)

	def ensure_sales_item(self):
		"""Reuse an invoice service; preserve historical per-crane products."""
		from heavy_equipment_rental.rental_items import default_service_item, validate_service_item

		if self.item:
			validate_service_item(self.item)
			if self.item == "CRANE-" + self.name:
				frappe.db.set_value("Item", self.item, "item_name", self.crane_name)
			return self.item
		self.item = default_service_item()
		frappe.db.set_value("Crane", self.name, "item", self.item, update_modified=False)
		return self.item

	def validate(self):
		if self.ownership_type == "Rented" and not self.supplier:
			frappe.throw(_("Select a Supplier for a rented Crane."))
		if self.crane_image and "/private/files/" in self.crane_image:
			frappe.throw(_("The Crane image must be public. Upload it from the sidebar."))
		self.crane_list_image = self.crane_image
		before = self.get_doc_before_save()
		if before and self.item != before.item:
			frappe.throw(_("The linked sales Item cannot be changed manually."))
		if before and self.operational_condition != before.operational_condition:
			# A manual condition change takes ownership away from the maintenance log.
			self.maintenance_condition_managed = 0
		check_non_negative(self.capacity_tons, _("Capacity"))
		if not self.is_new():
			lock_cranes([self.name])
		periods = set()
		for row in self.period_prices:
			if row.period not in ("Hour", "Day", "Month") or row.period in periods:
				frappe.throw(_("Crane prices must contain Hour, Day and Month exactly once."))
			periods.add(row.period)
			check_non_negative(row.price, _("{0} price").format(row.period))
		for period in ("Hour", "Day", "Month"):
			if period not in periods:
				row = self.append("period_prices", {"period": period, "price": 0})
				# Validation runs after Frappe names existing children on insert.
				if self.is_new():
					set_new_name(row)
		self.period_prices.sort(key=lambda row: ("Hour", "Day", "Month").index(row.period))
		for index, row in enumerate(self.period_prices, 1):
			row.idx = index
		from heavy_equipment_rental.profit_sharing import validate_agreement

		validate_agreement(self)
		from heavy_equipment_rental.crane_assets import validate_asset_link

		validate_asset_link(self)
		# Physical condition remains independent of bookings, including when
		# maintenance starts during an existing contract. New activation is blocked.
