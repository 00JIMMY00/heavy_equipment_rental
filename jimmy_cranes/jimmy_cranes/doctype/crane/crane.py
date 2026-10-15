import frappe
from frappe import _
from frappe.model.document import Document

from jimmy_cranes.rental_validation import check_non_negative, lock_cranes


class Crane(Document):
	def after_insert(self):
		self.ensure_sales_item()

	def on_update(self):
		self.ensure_sales_item()

	def ensure_sales_item(self):
		"""Create the service item in the same transaction as the crane."""
		if self.item:
			if not frappe.db.exists("Item", self.item):
				frappe.throw(_("The linked sales Item for crane {0} is missing.").format(self.crane_name))
			if frappe.db.get_value("Item", self.item, "item_name") != self.crane_name:
				frappe.db.set_value("Item", self.item, "item_name", self.crane_name)
			return self.item
		code = "CRANE-" + self.name
		if frappe.db.exists("Item", code):
			frappe.throw(_("Item {0} already exists; choose a distinct crane code.").format(code))
		if not frappe.db.exists("UOM", "Hour"):
			frappe.throw(_("Create the Hour UOM before saving cranes."))
		item_group = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value(
			"Item Group", {"is_group": 0}, "name"
		)
		if not item_group:
			frappe.throw(_("Create a service Item Group before saving cranes."))
		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": code,
			"item_name": self.crane_name,
			"item_group": item_group,
			"stock_uom": "Hour",
			"is_stock_item": 0,
			"is_sales_item": 1,
		})
		item.insert(ignore_permissions=True)
		self.item = item.name
		frappe.db.set_value("Crane", self.name, "item", item.name, update_modified=False)
		return item.name

	def validate(self):
		before = self.get_doc_before_save()
		if before and self.item != before.item:
			frappe.throw(_("The linked sales Item cannot be changed manually."))
		check_non_negative(self.capacity_tons, _("Capacity"))
		if not self.is_new():
			lock_cranes([self.name])
		periods = set()
		for row in self.period_prices:
			if row.period not in ("Day", "Month", "Year") or row.period in periods:
				frappe.throw(_("Crane prices must contain Day, Month and Year exactly once."))
			periods.add(row.period)
			check_non_negative(row.price, _("{0} price").format(row.period))
		for period in ("Day", "Month", "Year"):
			if period not in periods:
				self.append("period_prices", {"period": period, "price": 0})
		self.period_prices.sort(key=lambda row: ("Day", "Month", "Year").index(row.period))
		for index, row in enumerate(self.period_prices, 1):
			row.idx = index
		# Physical condition remains independent of bookings, including when
		# maintenance starts during an existing contract. New activation is blocked.
