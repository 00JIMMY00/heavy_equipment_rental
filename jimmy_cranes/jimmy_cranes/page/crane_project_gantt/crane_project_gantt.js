frappe.pages["crane-project-gantt"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Crane Reservations and Work"),
		single_column: true,
	});
	const state = {
		project: null,
		crane: null,
		status: "",
		from_date: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
		to_date: frappe.datetime.add_days(frappe.datetime.get_today(), 90),
		zoom: "Day",
		search: "",
		data: null,
	};
	const fields = {};
	fields.project = page.add_field({
		fieldname: "project",
		label: __("Project"),
		fieldtype: "Link",
		options: "Project",
		change: () => {
			state.project = fields.project.get_value();
			load();
		},
	});
	fields.crane = page.add_field({
		fieldname: "crane",
		label: __("Crane"),
		fieldtype: "Link",
		options: "Crane",
		change: () => {
			state.crane = fields.crane.get_value();
			load();
		},
	});
	fields.status = page.add_field({
		fieldname: "status",
		label: __("Allocation Status"),
		fieldtype: "Select",
		options: "\nDraft\nReserved\nReleased\nCancelled",
		change: () => {
			state.status = fields.status.get_value();
			load();
		},
	});
	fields.from_date = page.add_field({
		fieldname: "from_date",
		label: __("From"),
		fieldtype: "Date",
		default: state.from_date,
		change: () => {
			state.from_date = fields.from_date.get_value();
			load();
		},
	});
	fields.to_date = page.add_field({
		fieldname: "to_date",
		label: __("To"),
		fieldtype: "Date",
		default: state.to_date,
		change: () => {
			state.to_date = fields.to_date.get_value();
			load();
		},
	});
	page.set_primary_action(__("Refresh"), load, "refresh");
	page.main.append(`<style>
		.crane-gantt-controls {display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0}
		.crane-gantt-controls input {max-width:220px}
		.crane-gantt-legend {display:flex;gap:18px;flex-wrap:wrap;color:var(--text-muted);font-size:12px}
		.crane-gantt-legend i {display:inline-block;width:16px;height:9px;margin-right:5px;border-radius:4px}
		.crane-gantt-scroll {overflow:auto;max-height:calc(100vh - 300px);border:1px solid var(--border-color);border-radius:6px}
		.crane-gantt-row {display:flex;min-height:60px;border-bottom:1px solid var(--border-color);width:max-content}
		.crane-gantt-row.header {position:sticky;top:0;z-index:5;background:var(--card-bg);min-height:46px}
		.crane-gantt-label {position:sticky;left:0;z-index:2;width:210px;min-width:210px;padding:8px 10px;background:var(--card-bg);border-right:1px solid var(--border-color);font-size:12px}
		.crane-gantt-row.header .crane-gantt-label {z-index:6;font-weight:600}
		.crane-gantt-label small {display:block;color:var(--text-muted)}
		.crane-gantt-track {position:relative;flex:none;background:repeating-linear-gradient(to right,transparent 0,transparent calc(var(--day-width) - 1px),var(--border-color) calc(var(--day-width) - 1px),var(--border-color) var(--day-width))}
		.crane-gantt-month {position:absolute;top:2px;font-weight:600;font-size:11px;white-space:nowrap}
		.crane-gantt-tick {position:absolute;top:22px;font-size:10px;color:var(--text-muted);white-space:nowrap}
		.crane-gantt-bar {position:absolute;height:12px;border-radius:4px;cursor:pointer;min-width:3px}
		.crane-gantt-bar.planned {top:10px;background:#5b8def;opacity:.8}
		.crane-gantt-bar.actual {top:28px;background:#2eab72}
		.crane-gantt-bar.draft {opacity:.35} .crane-gantt-bar.reserved {background:#5b8def} .crane-gantt-bar.released {background:#2eab72} .crane-gantt-bar.cancelled {background:#9ba1a6;opacity:.4;text-decoration:line-through} .crane-gantt-unknown {position:absolute;font-size:10px;color:var(--text-muted)}
		.crane-gantt-dot {position:absolute;top:44px;width:10px;height:10px;border:0;border-radius:50%;background:#9656b7;cursor:pointer;transform:translateX(-50%);padding:0}
		.crane-gantt-dot.draft {background:#e59b3b}
		.crane-gantt-empty {padding:24px;color:var(--text-muted)}
	</style><div class="crane-gantt-controls"></div><div class="crane-gantt-legend"></div><div class="crane-gantt-scroll"></div>`);
	const $controls = page.main.find(".crane-gantt-controls");
	const $scroll = page.main.find(".crane-gantt-scroll");
	const $legend = page.main.find(".crane-gantt-legend");
	$controls.html(`<label>${__("Zoom")}
		<select class="form-control input-sm crane-gantt-zoom">
			<option>Day</option><option>Week</option><option>Month</option>
		</select></label><input class="form-control input-sm crane-gantt-search" placeholder="${__("Find crane")}">`);
	$legend.html(`<span><i style="background:#5b8def"></i>${__("Reserved / planned")}</span>
		<span><i style="background:#2eab72"></i>${__("Released / occupied period")}</span>
		<span><i style="background:#9656b7"></i>${__("Worked day")}</span>
		<span><i style="background:#e59b3b"></i>${__(
			"Draft work"
		)}</span><span><i style="background:#9ba1a6"></i>${__("Cancelled / provisional Draft")}</span>`);
	$controls.on("change", ".crane-gantt-zoom", (event) => {
		state.zoom = event.currentTarget.value;
		render();
	});
	$controls.on("input", ".crane-gantt-search", (event) => {
		state.search = event.currentTarget.value.toLowerCase();
		render();
	});
	$scroll.on("click", ".crane-gantt-bar", (event) => {
		frappe.set_route("Form", "Crane Assignment", event.currentTarget.dataset.assignment);
	});
	$scroll.on("click", ".crane-gantt-dot", (event) => {
		const crane = event.currentTarget.dataset.crane;
		const date = event.currentTarget.dataset.date;
		const lane = (state.data.cranes || []).find((item) => item.crane === crane);
		const marker = lane && lane.work.find((item) => item.date === date);
		if (!marker) return;
		if (marker.timesheets.length === 1) {
			frappe.set_route("Form", "Crane Timesheet", marker.timesheets[0]);
		} else {
			const links = marker.timesheets
				.map(
					(name) => `<a href="/app/crane-timesheet/${encodeURIComponent(name)}">${escape(name)}</a>`
				)
				.join("<br>");
			frappe.msgprint({ title: __("Timesheets on {0}", [date]), message: links });
		}
	});

	function escape(value) {
		return frappe.utils.escape_html(String(value == null ? "" : value));
	}
	function day(value) {
		return new Date(String(value).slice(0, 10) + "T00:00:00Z");
	}
	function days_between(a, b) {
		return Math.round((day(b) - day(a)) / 86400000);
	}
	function date_at(start, offset) {
		const date = day(start);
		date.setUTCDate(date.getUTCDate() + offset);
		return date.toISOString().slice(0, 10);
	}
	let request_id = 0;
	function load() {
		if (!state.from_date || !state.to_date) {
			$scroll.html(
				`<div class="crane-gantt-empty">${__(
					"Choose dates; optionally filter by Project or crane."
				)}</div>`
			);
			return;
		}
		$scroll.html(`<div class="crane-gantt-empty">${__("Loading timeline...")}</div>`);
		const current_request = ++request_id;
		frappe.call({
			method: "jimmy_cranes.rental_queries.get_project_timeline",
			args: {
				project: state.project,
				from_date: state.from_date,
				to_date: state.to_date,
				crane: state.crane,
				status: state.status,
			},
			callback: (result) => {
				if (current_request === request_id) {
					state.data = result.message;
					render();
				}
			},
		});
	}
	function render() {
		if (!state.data) return;
		const { from_date, to_date } = state.data;
		const days = days_between(from_date, to_date) + 1;
		const width = { Day: 28, Week: 12, Month: 5 }[state.zoom];
		const track_width = days * width;
		const lanes = state.data.cranes.filter((item) =>
			(item.crane + " " + item.crane_name).toLowerCase().includes(state.search)
		);
		if (!lanes.length) {
			$scroll.html(
				`<div class="crane-gantt-empty">${__("No crane activity in this date range.")}</div>`
			);
			return;
		}
		const header = [];
		for (let i = 0; i < days; i++) {
			const date = date_at(from_date, i);
			const label = day(date);
			if (i === 0 || label.getUTCDate() === 1) {
				header.push(
					`<span class="crane-gantt-month" style="left:${i * width}px">${escape(
						label.toLocaleString(undefined, {
							month: "short",
							year: "numeric",
							timeZone: "UTC",
						})
					)}</span>`
				);
			}
			if (i % (state.zoom === "Day" ? 7 : state.zoom === "Week" ? 14 : 30) === 0) {
				header.push(
					`<span class="crane-gantt-tick" style="left:${i * width}px">${escape(date)}</span>`
				);
			}
		}
		const html = [
			`<div class="crane-gantt-row header"><div class="crane-gantt-label">${__(
				"Crane"
			)}</div><div class="crane-gantt-track" style="width:${track_width}px;--day-width:${width}px">${header.join(
				""
			)}</div></div>`,
		];
		for (const lane of lanes) {
			const parts = [];
			let segment_index = 0;
			const work_top = lane.segments.length * 40 + 8;
			function bar(start, end, css, segment, title) {
				if (!start || !end || end < from_date || start > to_date) return;
				const left = Math.max(0, days_between(from_date, start)) * width;
				const right = Math.min(days - 1, days_between(from_date, end));
				const bar_width = Math.max(
					3,
					(right - Math.max(0, days_between(from_date, start)) + 1) * width
				);
				parts.push(`<div class="crane-gantt-bar ${css}" style="left:${left}px;width:${bar_width}px;top:${
					segment_index * 40 + (css === "actual" ? 24 : 8)
				}px"
					title="${escape(title)}" data-assignment="${escape(segment.assignment)}"></div>`);
			}
			for (const segment of lane.segments) {
				const id = `${segment.project} · ${segment.assignment} · ${segment.row_status}`;
				bar(
					segment.start_date,
					segment.end_date,
					"planned " + segment.row_status.toLowerCase().replaceAll(" ", "-"),
					segment,
					`${id} | ${__("Planned")}: ${segment.start_date} – ${segment.end_date}`
				);
				if (segment.row_status === "Released" && segment.actual_end_date) {
					bar(
						segment.start_date,
						segment.actual_end_date,
						"actual",
						segment,
						`${id} | ${__("Occupied period")}: ${segment.start_date} – ${segment.actual_end_date}`
					);
				}
				if (segment.overdue)
					parts.push(
						`<span class="crane-gantt-unknown" style="top:${segment_index * 40 + 23}px;left:${
							Math.max(0, days_between(from_date, segment.start_date)) * width
						}px">${__("Overdue / release confirmation needed")}</span>`
					);
				segment_index++;
			}
			for (const marker of lane.work) {
				const offset = days_between(from_date, marker.date);
				const draft = marker.statuses.includes("Draft");
				const title = `${marker.date} | ${__("Work recorded")}: ${marker.operator_hours} ${__(
					"Operator Hours"
				)} | ${marker.statuses.join(", ")} | ${marker.timesheets.join(", ")}`;
				parts.push(`<button type="button" class="crane-gantt-dot${
					draft ? " draft" : ""
				}" style="left:${(offset + 0.5) * width}px;top:${work_top}px"
					title="${escape(title)}" data-crane="${escape(lane.crane)}" data-date="${escape(marker.date)}"></button>`);
			}
			html.push(`<div class="crane-gantt-row"><div class="crane-gantt-label">${escape(
				lane.crane_name
			)}${[...new Set(lane.segments.map((s) => s.project))]
				.map((p) => `<small><a href="/app/project/${encodeURIComponent(p)}">${escape(p)}</a></small>`)
				.join("")}</div>
				<div class="crane-gantt-track" style="width:${track_width}px;min-height:${Math.max(
				62,
				work_top + 20
			)}px;--day-width:${width}px">${parts.join("")}</div></div>`);
		}
		$scroll.html(html.join(""));
	}

	frappe.pages["crane-project-gantt"].on_page_show = () => {
		const route = frappe.get_route();
		if (frappe.route_options?.crane) {
			state.crane = frappe.route_options.crane;
			fields.crane.set_value(state.crane);
			frappe.route_options = null;
		}
		if ((route[1] || "") !== (state.project || "")) {
			state.project = route[1] || "";
			fields.project.set_value(state.project);
		} else {
			load();
		}
	};
};
