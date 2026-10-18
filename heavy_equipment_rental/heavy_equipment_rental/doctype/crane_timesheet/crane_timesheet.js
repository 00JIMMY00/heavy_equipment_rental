function fill_default_days(frm) {
	if (frm.doc.docstatus !== 0 || !frm.doc.period_start || !frm.doc.period_end) return;
	const start = frm.doc.period_start;
	const end = frm.doc.period_end;
	const request = (frm._default_days_request || 0) + 1;
	frm._default_days_request = request;
	frappe
		.call({
			method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet.default_timesheet_entries",
			args: { period_start: start, period_end: end },
		})
		.then(({ message: defaults }) => {
			if (
				request !== frm._default_days_request ||
				frm.doc.period_start !== start ||
				frm.doc.period_end !== end
			)
				return;
			const existing = new Set((frm.doc.timesheet_entries || []).map((row) => row.work_date));
			let added = false;
			for (const values of defaults || []) {
				if (existing.has(values.work_date)) continue;
				frm.add_child("timesheet_entries", values);
				existing.add(values.work_date);
				added = true;
			}
			if (added) frm.refresh_field("timesheet_entries");
		});
}

frappe.ui.form.on("Crane Timesheet", {
	setup(frm) {
		frm.set_query("crane", () => ({
			query: "heavy_equipment_rental.rental_queries.assigned_crane_query",
			filters: {
				project: frm.doc.project,
				work_date: frm.doc.timesheet_entries?.[0]?.work_date || frm.doc.period_start,
			},
		}));
	},
	project(frm) {
		frm.set_value("crane", null);
	},
	period_start: fill_default_days,
	period_end: fill_default_days,
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !(frm.doc.timesheet_entries || []).length) fill_default_days(frm);
		if (frm.doc.docstatus === 1 && frappe.model.can_create("Sales Invoice"))
			frm.add_custom_button(__("Generate Sales Invoice"), () => frappe.call({
				method: "heavy_equipment_rental.billing.generate_sales_invoice",
				args: { timesheet: frm.doc.name },
				freeze: true,
				callback: ({ message }) => {
					if (message?.name) frappe.set_route("Form", "Sales Invoice", message.name);
				},
			}), __("Create"));
	},
});
