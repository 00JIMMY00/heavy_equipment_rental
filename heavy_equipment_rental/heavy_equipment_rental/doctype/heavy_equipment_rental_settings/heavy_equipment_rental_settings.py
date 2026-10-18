from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time


class HeavyEquipmentRentalSettings(Document):
	def validate(self):
		if not self.day_shift_start_time or not self.day_shift_end_time:
			frappe.throw(_("Enter both default day shift times."))
		start = datetime.combine(datetime(2000, 1, 1).date(), get_time(self.day_shift_start_time))
		end = datetime.combine(datetime(2000, 1, 1).date(), get_time(self.day_shift_end_time))
		if end <= start:
			frappe.throw(_("The default day shift end must be after its start on the same day."))
		self.day_shift_hours = (end - start).total_seconds() / 3600
