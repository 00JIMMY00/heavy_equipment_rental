frappe.ui.form.on("Crane Timesheet", {
	setup(frm) {
		frm.set_query("crane", () => ({
			query: "jimmy_cranes.rental_queries.assigned_crane_query",
			filters: {
				project: frm.doc.project,
				work_date: frm.doc.timesheet_entries?.[0]?.work_date || frm.doc.period_start,
			},
		}));
	},
	project(frm) {
		if (!frm.doc.legacy_snapshot) frm.set_value("crane", null);
	},
	refresh(frm) {
		if (frm.doc.legacy_needs_review)
			frm.set_intro(
				__(
					"Original hours and approval state are preserved below. Enter verified shift times and hourly prices, then save before submitting."
				),
				"orange"
			);
	},
});
