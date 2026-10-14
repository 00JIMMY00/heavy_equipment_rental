frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new() || !frappe.model.can_read("Crane Assignment")) return;
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
		frm.add_custom_button(
			__("Fleet Reservations"),
			() => frappe.set_route("crane-project-gantt", frm.doc.name),
			__("View")
		);
		if (frm.doc.status === "Open" && frm.perm[0]?.write && frappe.model.can_create("Crane Assignment"))
			frm.add_custom_button(
				__("Crane Assignment"),
				() => frappe.new_doc("Crane Assignment", { project: frm.doc.name }),
				__("Create")
			);
		frappe
			.call({ method: "jimmy_cranes.rental_queries.project_overview", args: { project: frm.doc.name } })
			.then(({ message: rows }) => {
				$(frm.dashboard.parent).find(".crane-project-section").remove();
				if (!rows?.length) return;
				const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
				const body = rows
					.map(
						(row) => `<tr>
					<td>${esc(row.crane_name)}</td>
					<td><a href="/app/crane-assignment/${encodeURIComponent(row.assignment)}">${esc(row.assignment)}</a></td>
					<td>${esc(row.start_date)}</td><td>${esc(row.expected_end_date)}</td>
					<td>${esc(row.actual_end_date) || "—"}</td><td>${esc(__(row.status))}</td>
				</tr>`
					)
					.join("");
				const html = `<div class="crane-project-overview table-responsive" style="max-height:450px;overflow:auto">
					<table class="table table-bordered"><thead><tr>${[
						"Crane Name",
						"Assignment",
						"Start",
						"Expected End",
						"Actual Release",
						"Status",
					]
						.map((h) => `<th>${__(h)}</th>`)
						.join("")}</tr></thead>
					<tbody>${body}</tbody></table></div>`;
				frm.dashboard.add_section(html, __("Assigned Cranes"), "crane-project-section");
			});
	},
});
