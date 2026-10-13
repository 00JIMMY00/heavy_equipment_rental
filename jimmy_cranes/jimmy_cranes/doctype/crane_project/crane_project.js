frappe.ui.form.on("Crane Project", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.perm[0]?.write && !frm.is_dirty()) {
			const actions = {
				Draft: ["Reserve", "Start"],
				Reserved: ["Start"],
				"In Progress": ["Complete"],
			};
			(actions[frm.doc.status] || []).forEach((action) =>
				frm.add_custom_button(
					__(action),
					() => {
						const run = (values) =>
							frappe
								.call({
									method: "jimmy_cranes.rental_operations.project_action",
									args: { project: frm.doc.name, action, ...values },
									freeze: true,
								})
								.then(() => frm.reload_doc());
						if (action === "Complete")
							frappe.prompt(
								{
									fieldname: "date",
									fieldtype: "Date",
									label: __("Completion Date"),
									default: frappe.datetime.get_today(),
									reqd: 1,
								},
								run,
								__("Complete Project")
							);
						else run({});
					},
					__("Actions")
				)
			);
		}
		frm.add_custom_button(
			__("Gantt Chart"),
			() => frappe.set_route("crane-project-gantt", frm.doc.name),
			__("View")
		);
		frm.add_custom_button(
			__("Crane Assignments"),
			() => frappe.set_route("List", "Crane Assignment", { project: frm.doc.name }),
			__("View")
		);
		frm.add_custom_button(
			__("Crane Timesheets"),
			() => frappe.set_route("List", "Crane Timesheet", { project: frm.doc.name }),
			__("View")
		);
		if (frm.doc.status !== "Complete")
			frm.add_custom_button(
				__("Crane Assignment"),
				() => frappe.new_doc("Crane Assignment", { project: frm.doc.name }),
				__("Create")
			);
		if (
			frm.doc.legacy_erpnext_project &&
			frm.doc.status === "Complete" &&
			!frm.doc.completion_date &&
			(frappe.user.has_role("System Manager") || frappe.user.has_role("Projects Manager"))
		) {
			frm.set_intro(
				__(
					"Review actual dates on legacy assignments, then enter the verified Project completion date."
				),
				"orange"
			);
			frm.add_custom_button(
				__("Review Completion Date"),
				() =>
					frappe.prompt(
						{
							fieldname: "date",
							fieldtype: "Date",
							label: __("Verified Completion Date"),
							reqd: 1,
						},
						(values) =>
							frappe
								.call({
									method: "jimmy_cranes.rental_operations.review_project_completion",
									args: { project: frm.doc.name, date: values.date },
									freeze: true,
								})
								.then(() => frm.reload_doc())
					),
				__("Actions")
			);
		}
		const esc = (value) => frappe.utils.escape_html(String(value || ""));
		frappe
			.call({
				method: "jimmy_cranes.rental_queries.project_overview",
				args: { project: frm.doc.name },
			})
			.then(({ message: rows }) => {
				const body = (rows || [])
					.map(
						(row) =>
							`<tr><td>${esc(
								row.crane
							)}</td><td><a href="/app/crane-assignment/${encodeURIComponent(
								row.assignment
							)}">${esc(row.assignment)}</a></td><td>${esc(
								row.start_date
							)}</td><td>${esc(row.expected_end_date)}</td><td>${
								esc(row.actual_end_date) ||
								(row.legacy_needs_review ? __("Unknown — review required") : "—")
							}</td><td>${esc(row.status)}</td></tr>`
					)
					.join("");
				frm.fields_dict.assigned_cranes_overview.$wrapper.html(
					`<div class="table-responsive" style="max-height:450px;overflow:auto"><table class="table table-bordered"><thead><tr>${[
						"Crane",
						"Assignment",
						"Planned Start",
						"Expected End",
						"Actual End",
						"Status",
					]
						.map((h) => `<th>${__(h)}</th>`)
						.join("")}</tr></thead><tbody>${
						body || `<tr><td colspan="6">${__("No assigned cranes")}</td></tr>`
					}</tbody></table></div>`
				);
			});
	},
});
