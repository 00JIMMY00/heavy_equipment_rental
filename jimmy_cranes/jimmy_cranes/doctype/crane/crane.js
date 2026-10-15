frappe.ui.form.on("Crane", {
	onload(frm) {
		if (frm.is_new()) {
			for (const period of ["Hour", "Day", "Month", "Year"]) {
				if (!(frm.doc.period_prices || []).some((row) => row.period === period))
					frm.add_child("period_prices", { period, price: 0 });
			}
			frm.refresh_field("period_prices");
		}
		frm.fields_dict.period_prices.grid.cannot_add_rows = true;
		frm.fields_dict.period_prices.grid.cannot_delete_rows = true;
	},
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(
			__("Fleet Reservations"),
			() => {
				frappe.route_options = { crane: frm.doc.name };
				frappe.set_route("crane-project-gantt");
			},
			__("View")
		);
		frm.trigger("availability_date");
	},
	availability_date(frm) {
		if (frm.is_new()) return;
		frappe
			.call({
				method: "jimmy_cranes.rental_queries.crane_availability",
				args: {
					crane: frm.doc.name,
					date: frm.doc.availability_date || frappe.datetime.get_today(),
				},
			})
			.then(({ message: data }) => {
				const esc = frappe.utils.escape_html;
				const rows = data.future_reservations
					.map(
						(row) =>
							`<tr><td><a href="/app/crane-project/${encodeURIComponent(row.project)}">${esc(
								row.project
							)}</a></td><td><a href="/app/crane-assignment/${encodeURIComponent(
								row.assignment
							)}">${esc(row.assignment)}</a></td><td>${esc(row.start_date)}</td><td>${esc(
								row.expected_end_date
							)}</td><td>${esc(row.status)}</td></tr>`
					)
					.join("");
				frm.fields_dict.availability_overview.$wrapper.html(
					`<p><b>${__("Availability")}:</b> ${
						data.available ? __("Available") : __("Unavailable")
					} · ${data.indicators.map((value) => esc(__(value))).join(" · ")}</p><p>${__(
						"Future reservations"
					)}: ${data.has_future_reservations ? __("Yes") : __("None")}</p>${
						rows
							? `<div class="table-responsive"><table class="table table-bordered"><thead><tr>${[
									"Project",
									"Assignment",
									"Start",
									"End",
									"Status",
							  ]
									.map((x) => `<th>${__(x)}</th>`)
									.join("")}</tr></thead><tbody>${rows}</tbody></table></div>`
							: ""
					}`
				);
			});
	},
});
