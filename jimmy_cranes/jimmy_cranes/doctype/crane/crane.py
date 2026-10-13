import frappe
from frappe import _
from frappe.model.document import Document

from jimmy_cranes.rental_validation import check_non_negative, lock_cranes, protect_legacy


class Crane(Document):
	def validate(self):
		check_non_negative(self.capacity_tons, _("Capacity"))
		protect_legacy(self, ("legacy_status",))
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
