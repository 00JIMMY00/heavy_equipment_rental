async function crane_names_for_rows(rows) {
	const codes = [...new Set(rows.map((row) => row.crane).filter(Boolean))];
	if (!codes.length) return {};
	const cranes = await frappe.db.get_list("Crane", {
		fields: ["name", "crane_name"],
		filters: { name: ["in", codes] },
		limit: codes.length,
	});
	return Object.fromEntries(cranes.map((crane) => [crane.name, crane.crane_name]));
}

frappe.ui.form.on("Crane Assignment", {
	refresh(frm) {
		frm.set_query("project", () => ({ filters: { status: ["!=", "Complete"] } }));
		const completed = Number(frm.doc.completed_cranes || 0);
		const total = Number(frm.doc.total_cranes || 0);
		const percentage = Math.max(0, Math.min(100, Number(frm.doc.completion_percentage || 0)));
		frm.get_field("completion_progress").$wrapper.html(`
			<div class="mb-2"><strong>${percentage.toFixed(1)}%</strong> · ${completed} / ${total} ${__("Cranes Completed")}</div>
			<div class="progress" role="progressbar" aria-label="${__("Crane completion")}" aria-valuenow="${percentage}" aria-valuemin="0" aria-valuemax="100">
				<div class="progress-bar" style="width: ${percentage}%"></div>
			</div>
		`);
		if (frm.is_new() || frm.is_dirty() || !frm.perm[0]?.write) return;
		const eligible = {
			Reserve: ["Draft"],
			Start: ["Draft", "Reserved"],
			Complete: ["In Progress"],
			Cancel: ["Draft", "Reserved", "In Progress"],
		};
		for (const action of Object.keys(eligible)) {
			const rows = (frm.doc.assigned_cranes || []).filter((row) =>
				eligible[action].includes(row.status)
			);
			if (!rows.length) continue;
			frm.add_custom_button(
				__(`${action} Cranes`),
				async () => {
					const crane_names = await crane_names_for_rows(rows);
					const dialog = new frappe.ui.Dialog({
						title: __(`${action} Cranes`),
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
								data: rows.map((row) => ({
									row_name: row.name,
									crane_name: crane_names[row.crane] || row.crane,
									start_date: row.start_date,
									expected_end_date: row.expected_end_date,
									status: row.status,
								})),
							},
							...(action === "Reserve"
								? []
								: [
										{
											fieldname: "date",
											fieldtype: "Date",
											label: __(
												action === "Complete"
													? "Actual Completion Date"
													: `${action} Date`
											),
											default: frappe.datetime.get_today(),
											reqd: 1,
										},
								  ]),
							...(["Complete", "Cancel"].includes(action)
								? [
										{
											fieldname: "reason",
											fieldtype: "Small Text",
											label: __(
												action === "Cancel"
													? "Cancellation Reason"
													: "Reason for Late Completion (if applicable)"
											),
											reqd: action === "Cancel",
											description:
												action === "Cancel"
													? __(
															"Cancellation is only for cranes with no recorded work. Complete cranes that participated."
													  )
													: __("Expected end dates remain unchanged."),
										},
								  ]
								: []),
						],
						primary_action_label: __(`${action} Selected Cranes`),
						primary_action(values) {
							const row_names = dialog.fields_dict.rows.grid
								.get_selected_children()
								.map((row) => row.row_name);
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
		const legacy = (frm.doc.assigned_cranes || []).filter(
			(row) => row.legacy_needs_review && row.status !== "Cancelled"
		);
		if (
			legacy.length &&
			(frappe.user.has_role("System Manager") || frappe.user.has_role("Projects Manager"))
		)
			frm.add_custom_button(
				__("Review Legacy Dates"),
				async () => {
					const crane_names = await crane_names_for_rows(legacy);
					frappe.prompt(
						[
							{
								fieldname: "row_name",
								fieldtype: "Select",
								label: __("Allocation"),
								options: legacy.map((r) => ({
									value: r.name,
									label: `${crane_names[r.crane] || r.crane} · ${r.start_date} — ${r.expected_end_date}`,
								})),
								reqd: 1,
							},
							{
								fieldname: "actual_start_date",
								fieldtype: "Date",
								label: __("Verified Actual Start"),
								reqd: 1,
							},
							{
								fieldname: "actual_end_date",
								fieldtype: "Date",
								label: __("Verified Actual End (completed rows)"),
							},
							{
								fieldname: "reason",
								fieldtype: "Small Text",
								label: __("Late Completion Reason"),
							},
						],
						(values) =>
							frappe
								.call({
									method: "jimmy_cranes.rental_operations.review_legacy_dates",
									args: {
										assignment: frm.doc.name,
										project: frm.doc.project,
										...values,
									},
									freeze: true,
								})
								.then(() => frm.reload_doc()),
						__("Review Legacy Dates")
					);
				},
				__("Actions")
			);
		frm.add_custom_button(
			__("Gantt Chart"),
			() => frappe.set_route("crane-project-gantt", frm.doc.project),
			__("View")
		);
	},
});
