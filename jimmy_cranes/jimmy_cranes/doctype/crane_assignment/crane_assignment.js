function render_crane_progress(frm) {
	const released = Number(frm.doc.released_cranes || 0);
	const total = Number(frm.doc.total_cranes || 0);
	const percent = Number(frm.doc.completion_percentage || 0);
	const caption = total ? __("{0} / {1} Released", [released, total]) : __("No active crane allocations");
	frm.get_field("completion_progress").$wrapper.html(`
		<div class="mb-2"><strong>${percent.toFixed(1)}%</strong> · ${caption}</div>
		<div class="progress" role="progressbar" aria-label="${__(
			"Crane releases"
		)}" aria-valuenow="${percent}" aria-valuemin="0" aria-valuemax="100">
			<div class="progress-bar" style="width:${percent}%"></div>
		</div>`);
}

frappe.ui.form.on("Crane Assignment", {
	refresh(frm) {
		frm.set_query("project", () => ({ filters: { status: "Open" } }));
		render_crane_progress(frm);
		if (frm.is_new() || frm.is_dirty()) return;
		frappe
			.call({
				method: "jimmy_cranes.rental_queries.assignment_summary",
				args: { assignment: frm.doc.name },
			})
			.then(({ message }) => {
				if (frm.is_dirty()) return;
				Object.assign(frm.doc, message);
				for (const field of Object.keys(message)) frm.refresh_field(field);
				render_crane_progress(frm);
			});
		frm.add_custom_button(
			__("Gantt Chart"),
			() => frappe.set_route("crane-project-gantt", frm.doc.project),
			__("View")
		);
		if (!frm.perm[0]?.write) return;
		const eligible = {
			Reserve: ["Draft"], Release: ["Reserved"], Cancel: ["Draft", "Reserved"],
			"Undo Reserve": ["Reserved"], "Undo Release": ["Released"], "Undo Cancel": ["Cancelled"],
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
										label: __("Expected End"),
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
							...(["Release", "Cancel"].includes(action)
								? [
										{
											fieldname: "date",
											fieldtype: "Date",
											label:
												action === "Release"
													? __("Actual Release Date")
													: __("Cancellation Date"),
											default: frappe.datetime.get_today(),
											reqd: 1,
										},
								  ]
								: []),
							...(["Cancel", "Undo Reserve", "Undo Release", "Undo Cancel"].includes(action)
								? [
										{
											fieldname: "reason",
											fieldtype: "Small Text",
											label: action === "Cancel" ? __("Cancellation Reason") : __("Correction Reason"),
											reqd: 1,
											description: action === "Cancel" ? __("If work is recorded, use Release instead.") : __("Saved in the assignment timeline."),
										},
								  ]
								: []),
							...(action === "Undo Cancel"
								? [{
									fieldname: "restore_status",
									fieldtype: "Select",
									label: __("Restore Status For Legacy Rows"),
									options: ["", "Draft", "Reserved"],
									description: __("Leave blank when the original status was recorded. Older cancelled rows need a choice."),
								}]
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
									method: "jimmy_cranes.rental_operations.crane_action",
									args: {
										assignment: frm.doc.name,
										project: frm.doc.project,
										row_names,
										action,
										date: values.date,
										reason: values.reason,
										restore_status: values.restore_status,
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
