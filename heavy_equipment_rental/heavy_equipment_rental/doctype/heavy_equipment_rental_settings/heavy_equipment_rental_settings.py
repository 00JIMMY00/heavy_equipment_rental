from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time

from heavy_equipment_rental.driver_payroll import validate_payroll_defaults


class HeavyEquipmentRentalSettings(Document):
	def validate(self):
		from heavy_equipment_rental.maintenance_posting import validate_repair_defaults
		for row in self.holiday_defaults:
			if bool(row.weekday) == bool(row.holiday_date):
				frappe.throw(_("Holiday row {0}: choose either a recurring weekday or a date.").format(row.idx))
		validate_repair_defaults(self)
		validate_payroll_defaults(self)
		from heavy_equipment_rental.consolidated_expenses import validate_defaults
		validate_defaults(self)
		if self.get("rental_service_item"):
			from heavy_equipment_rental.rental_items import validate_service_item
			validate_service_item(self.rental_service_item)
		if not self.day_shift_start_time or not self.day_shift_end_time:
			frappe.throw(_("Enter both default day shift times."))
		start = datetime.combine(datetime(2000, 1, 1).date(), get_time(self.day_shift_start_time))
		end = datetime.combine(datetime(2000, 1, 1).date(), get_time(self.day_shift_end_time))
		if end <= start:
			frappe.throw(_("The default day shift end must be after its start on the same day."))
		self.day_shift_hours = (end - start).total_seconds() / 3600
