frappe.pages["crane-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Crane Dashboard"), single_column: true });
	const $root = $('<div class="crane-dashboard"></div>').appendTo(page.main);
	const escape = (value) => frappe.utils.escape_html(String(value == null ? "" : value));
	const number = (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value || 0);
	const route = (doctype) => `/app/${frappe.router.slug(doctype)}`;
	const stat = (label, value, note, color) => `<div class="crane-stat" style="--accent:${color}"><div class="crane-stat-label">${__(label)}</div><div class="crane-stat-value">${number(value)}</div><div class="crane-stat-note">${__(note)}</div></div>`;
	function render(data) {
		const total = data.fleet_total || 1;
		const fleet = data.fleet.map((item) => {
			const condition = item.operational_condition;
			const kind = condition !== "Operational" ? "service" : item.reserved_today ? "busy" : "free";
			const status = condition !== "Operational" ? condition : item.reserved_today ? "Reserved" : "Available";
			return `<div class="crane-row"><div><strong>${escape(item.crane_name || item.name)}</strong><small>${escape(item.model || item.name)}${item.capacity_tons ? ` · ${number(item.capacity_tons)} ${__("tons")}` : ""}</small></div><span class="crane-pill ${kind}">${__(status)}</span></div>`;
		}).join("");
		const service = data.upcoming_maintenance.map((item) => `<div class="crane-row"><div><strong>${escape(item.crane)}</strong><small>${__(item.maintenance_type)} · ${escape(item.planned_start_date)}</small></div><span class="crane-pill service">${__(item.status)}</span></div>`).join("");
		$root.html(`
			<div class="crane-hero"><div><div class="crane-eyebrow">${__("Fleet operations")}</div><h1>${__("Your crane fleet at a glance")}</h1><p>${__("Live overview as of")} ${escape(data.as_of)}</p></div><a href="/app/crane-project-gantt">${__("View reservations")} ↗</a></div>
			<div class="crane-stats">
				${stat("Total cranes", data.fleet_total, "Across the fleet", "#1584a6")}
				${stat("Available today", data.available_today, "Operational and unreserved", "#22aa81")}
				${stat("Reserved today", data.reserved_today, "Active reservations", "#efa93d")}
				${stat("Open projects", data.open_projects, `${data.overdue_projects} overdue`, "#9c79e8")}
				${stat("Billable hours", data.hours_this_month, "Submitted this month", "#468de6")}
				${stat("Unbilled timesheets", data.unbilled_timesheets, "Submitted without invoice", "#f17b6e")}
				${stat("In maintenance", data.maintenance, "Fleet condition", "#db6883")}
				${stat("Upcoming services", data.upcoming_maintenance_count, "Next 14 days", "#4dafa8")}
			</div>
			<div class="crane-grid"><div>
				<div class="crane-panel"><h2>${__("Fleet condition")}</h2><p class="crane-panel-sub">${__("Operational readiness across all cranes")}</p><div class="crane-fleet-bar"><span style="width:${100 * data.operational / total}%;background:#22aa81"></span><span style="width:${100 * data.maintenance / total}%;background:#efa93d"></span><span style="width:${100 * data.inactive / total}%;background:#db6883"></span></div><div class="crane-legend"><span><i style="background:#22aa81"></i>${__("Operational")} ${number(data.operational)}</span><span><i style="background:#efa93d"></i>${__("Maintenance")} ${number(data.maintenance)}</span><span><i style="background:#db6883"></i>${__("Inactive")} ${number(data.inactive)}</span></div></div>
				<div class="crane-panel"><h2>${__("Fleet snapshot")}</h2><p class="crane-panel-sub">${__("Crane status for today")}</p>${fleet || `<div class="crane-empty">${__("No cranes have been added yet.")}</div>`}<a href="${route("Crane")}">${__("View all cranes")} →</a></div>
			</div><div>
				<div class="crane-panel"><h2>${__("Upcoming maintenance")}</h2><p class="crane-panel-sub">${__("Planned in the next 14 days")}</p>${service || `<div class="crane-empty">${__("No service scheduled soon.")}</div>`}<a href="${route("Crane Maintenance")}">${__("View maintenance")} →</a></div>
				<div class="crane-panel"><h2>${__("Quick actions")}</h2><p class="crane-panel-sub">${__("Jump into daily work")}</p><div class="crane-quicklinks"><a href="${route("Crane Project")}">${__("Projects")} →</a><a href="${route("Crane Assignment")}">${__("Assignments")} →</a><a href="${route("Crane Timesheet")}">${__("Timesheets")} →</a><a href="/app/crane-project-gantt">${__("Reservations")} →</a></div></div>
			</div></div>`);
	}
	async function load() {
		$root.html(`<div class="crane-panel">${__("Loading crane dashboard...")}</div>`);
		try {
			const response = await frappe.call({ method: "heavy_equipment_rental.dashboard.get_crane_dashboard" });
			render(response.message);
		} catch (error) {
			$root.html(`<div class="crane-panel">${__("Could not load the crane dashboard. Please refresh or check your permissions.")}</div>`);
		}
	}
	page.set_primary_action(__("Refresh"), load, "refresh");
	wrapper.crane_dashboard_load = load;
};
frappe.pages["crane-dashboard"].on_page_show = function (wrapper) {
	if (wrapper.crane_dashboard_load) wrapper.crane_dashboard_load();
};
