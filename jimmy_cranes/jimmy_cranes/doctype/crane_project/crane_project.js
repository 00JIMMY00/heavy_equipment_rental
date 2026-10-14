frappe.ui.form.on("Crane Project", {
	refresh(frm) {
		if (frm.is_new()) return;
		const links = [
			["Crane Assignments", "Crane Assignment"],
			["Crane Timesheets", "Crane Timesheet"],
		];
		links.forEach(([label, doctype]) => {
			if (frappe.model.can_read(doctype))
				frm.add_custom_button(__(label), () => frappe.set_route("List", doctype, { project: frm.doc.name }), __("View"));
		});
		frm.add_custom_button(__("Fleet Reservations"), () => frappe.set_route("crane-project-gantt", frm.doc.name), __("View"));
		if (frm.doc.status === "Open" && frm.perm[0]?.write) {
			if (frappe.model.can_create("Crane Assignment"))
				frm.add_custom_button(__("Crane Assignment"), () => frappe.new_doc("Crane Assignment", { project: frm.doc.name }), __("Create"));
			[["Complete Project", "Complete"], ["Cancel Project", "Cancel"]].forEach(([label, action]) =>
				frm.add_custom_button(__(label), () => frappe.call({
					method: "jimmy_cranes.rental_operations.project_action",
					args: { project: frm.doc.name, action },
					freeze: true,
					callback: () => frm.reload_doc(),
				}), __("Actions"))
			);
		}
		if (!frappe.model.can_read("Crane Assignment")) return;
		frappe.call({ method: "jimmy_cranes.rental_queries.project_overview", args: { project: frm.doc.name } })
			.then(({ message: rows }) => {
				$(frm.dashboard.parent).find(".crane-project-section").remove();
				if (!rows?.length) return;
				const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
				const body = rows.map((row) => `<tr><td>${esc(row.crane_name)}</td><td><a href="/app/crane-assignment/${encodeURIComponent(row.assignment)}">${esc(row.assignment)}</a></td><td>${esc(row.start_date)}</td><td>${esc(row.expected_end_date)}</td><td>${esc(row.actual_end_date) || "—"}</td><td>${esc(__(row.status))}</td></tr>`).join("");
				const headings = ["Crane Name", "Assignment", "Start", "Expected End", "Actual Release", "Status"].map((h) => `<th>${__(h)}</th>`).join("");
				frm.dashboard.add_section(`<div class="table-responsive"><table class="table table-bordered"><thead><tr>${headings}</tr></thead><tbody>${body}</tbody></table></div>`, __("Assigned Cranes"), "crane-project-section");
			});
	},
});
