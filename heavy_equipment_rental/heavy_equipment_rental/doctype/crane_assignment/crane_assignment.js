frappe.ui.form.on("Crane Assignment", {
	refresh(frm) {
		frm.set_query("project", () => ({ filters: { status: "Open" } }));
		if (frm.is_new() || frm.is_dirty()) return;
		frm.add_custom_button(
			__("Resource Calendar"),
			() => {
				const rows = frm.doc.assigned_cranes || [];
				const params = new URLSearchParams({ project: frm.doc.project });
				const from = rows.length ? rows.map((r) => r.start_date).filter(Boolean).sort()[0] : frm.doc.project_start_date;
				const to = rows.length ? rows.map((r) => r.expected_end_date).filter(Boolean).sort().at(-1) : frm.doc.project_end_date;
				if (from && to && (new Date(`${to}T12:00:00`) - new Date(`${from}T12:00:00`)) / 86400000 <= 120) {
					params.set("from", from);
					params.set("to", to);
				}
				window.location.href = `/rental-calendar/timeline?${params}`;
			},
			__("View")
		);
		if (!frm.perm[0]?.write) return;
		const eligible = {
			Reserve: ["Draft"], Cancel: ["Draft", "Reserved"],
			"Undo Reserve": ["Reserved"], "Undo Cancel": ["Cancelled"],
		};
		for (const [action, states] of Object.entries(eligible)) {
			const rows = (frm.doc.assigned_cranes || []).filter((row) => states.includes(row.status));
			if (!rows.length) continue;
			frm.add_custom_button(
				__(`${action} Selected`),
				async () => {
					const codes = [...new Set(rows.map((r) => r.crane))];
					const cranes = await frappe.db.get_list("Crane", {
						fields: ["name", "crane_name"],
						filters: { name: ["in", codes] },
						limit: codes.length,
					});
					const names = Object.fromEntries(cranes.map((r) => [r.name, r.crane_name]));
					const dialog = new frappe.ui.Dialog({
						title: __(`${action} Selected`),
						size: "extra-large",
						fields: [
							{
								fieldname: "rows",
								fieldtype: "Table",
								label: __("Select Crane Rows"),
								cannot_add_rows: true,
								cannot_delete_rows: true,
								in_place_edit: false,
								fields: [
									{ fieldname: "row_name", fieldtype: "Data", hidden: 1 },
									{
										fieldname: "crane_name",
										fieldtype: "Data",
										label: __("Crane Name"),
										in_list_view: 1,
										read_only: 1,
									},
									{
										fieldname: "start_date",
										fieldtype: "Date",
										label: __("Start"),
										in_list_view: 1,
										read_only: 1,
									},
									{
										fieldname: "expected_end_date",
										fieldtype: "Date",
										label: __("End"),
										in_list_view: 1,
										read_only: 1,
									},
									{
										fieldname: "status",
										fieldtype: "Data",
										label: __("Status"),
										in_list_view: 1,
										read_only: 1,
									},
								],
								data: rows.map((r) => ({
									row_name: r.name,
									crane_name: names[r.crane] || r.crane,
									start_date: r.start_date,
									expected_end_date: r.expected_end_date,
									status: r.status,
								})),
							},
							...(action === "Cancel"
								? [
										{
											fieldname: "date",
											fieldtype: "Date",
											label: __("Cancellation Date"),
											default: frappe.datetime.get_today(),
											reqd: 1,
										},
								  ]
								: []),
							...(["Cancel", "Undo Reserve", "Undo Cancel"].includes(action)
								? [
										{
											fieldname: "reason",
											fieldtype: "Small Text",
											label: action === "Cancel" ? __("Cancellation Reason") : __("Correction Reason"),
											reqd: 1,
											description: action === "Cancel" ? __("Only bookings without recorded work can be cancelled.") : __("Saved in the assignment timeline."),
										},
								  ]
								: []),
						],
						primary_action_label: __(`${action} Selected`),
						primary_action(values) {
							const row_names = dialog.fields_dict.rows.grid
								.get_selected_children()
								.map((r) => r.row_name);
							if (!row_names.length)
								return frappe.msgprint(
									__("Select at least one crane row using the checkboxes.")
								);
							frappe
								.call({
									method: "heavy_equipment_rental.rental_operations.crane_action",
									args: {
										assignment: frm.doc.name,
										project: frm.doc.project,
										row_names,
										action,
										date: values.date,
										reason: values.reason,
									},
									freeze: true,
								})
								.then(() => {
									dialog.hide();
									frm.reload_doc();
								});
						},
					});
					dialog.show();
				},
				__("Actions")
			);
		}
	},
});
