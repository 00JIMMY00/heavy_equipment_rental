frappe.pages["crane-project-gantt"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Crane Reservations and Work"),
		single_column: true,
	});
	const state = {
		project: null,
		assignment: null,
		crane: null,
		status: "",
		from_date: null,
		to_date: null,
		zoom: "Day",
		search: "",
		data: null,
		updating_fields: false,
	};
	const fields = {};
	fields.project = page.add_field({
		fieldname: "project",
		label: __("Crane Project"),
		fieldtype: "Link",
		options: "Crane Project",
		change: async () => {
			if (state.updating_fields) return;
			const value = fields.project.get_value() || "";
			if (value === (state.project || "")) return;
			state.project = value;
			state.assignment = null;
			await use_project_dates();
			choose_zoom();
			load();
		},
	});
	fields.crane = page.add_field({
		fieldname: "crane",
		label: __("Crane"),
		fieldtype: "Link",
		options: "Crane",
		change: () => {
			if (state.updating_fields) return;
			const value = fields.crane.get_value() || "";
			if (value === (state.crane || "")) return;
			state.crane = value;
			load();
		},
	});
	fields.status = page.add_field({
		fieldname: "status",
		label: __("Allocation Status"),
		fieldtype: "Select",
		options: "\nDraft\nReserved\nCancelled",
		change: () => {
			if (state.updating_fields) return;
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
			if (state.updating_fields) return;
			const value = fields.from_date.get_value();
			if (value === state.from_date) return;
			state.from_date = value;
			load();
		},
	});
	fields.to_date = page.add_field({
		fieldname: "to_date",
		label: __("To"),
		fieldtype: "Date",
		default: state.to_date,
		change: () => {
			if (state.updating_fields) return;
			const value = fields.to_date.get_value();
			if (value === state.to_date) return;
			state.to_date = value;
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
		.crane-gantt-bar.draft {opacity:.35} .crane-gantt-bar.reserved {background:#5b8def} .crane-gantt-bar.cancelled {background:#9ba1a6;opacity:.4;text-decoration:line-through}
		.crane-gantt-dot {position:absolute;top:44px;width:10px;height:10px;border:0;border-radius:50%;background:#9656b7;cursor:pointer;transform:translateX(-50%);padding:0}
		.crane-gantt-dot.draft {background:#e59b3b}
		.crane-gantt-empty {padding:38px;text-align:center;color:#6c8193;font-size:13px}
		.crane-gantt-hero {position:relative;overflow:hidden;margin:18px 0 15px;padding:25px 29px;background:linear-gradient(115deg,#183451,#25536d 65%,#2d777a);border-radius:17px;color:#fff;box-shadow:0 12px 28px rgba(28,69,91,.16)}
		.crane-gantt-hero:after {content:"";position:absolute;right:-90px;top:-130px;width:350px;height:350px;border:1px solid rgba(255,255,255,.18);border-radius:50%;box-shadow:0 0 0 52px rgba(255,255,255,.04),0 0 0 104px rgba(255,255,255,.025);pointer-events:none}
		.crane-gantt-eyebrow {font-size:11px;letter-spacing:.15em;text-transform:uppercase;font-weight:700;color:#a9e8df;margin-bottom:8px}
		.crane-gantt-hero h2 {margin:0 0 8px;font-size:25px;line-height:1.2;font-weight:700;color:#fff}
		.crane-gantt-hero p {margin:0;color:#d5e7ed;font-size:13px}
		.crane-gantt-cards {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}
		.crane-gantt-card {background:#fff;border:1px solid #dce7ee;border-radius:13px;padding:15px 17px;box-shadow:0 4px 16px rgba(32,64,96,.04)}
		.crane-gantt-card:before {content:"";display:block;width:24px;height:3px;border-radius:3px;background:#4b80da;margin-bottom:12px}
		.crane-gantt-card.work:before {background:#24a486}.crane-gantt-card.due:before {background:#e1a042}
		.crane-gantt-card strong {display:block;font-size:25px;line-height:1.1;font-variant-numeric:tabular-nums;color:#1b354f}
		.crane-gantt-card span {display:block;margin-top:5px;font-size:12px;color:#657b90}
		.crane-gantt-toolbar {display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap;margin-bottom:12px}
		.crane-gantt-toolbar h3 {font-size:16px;font-weight:700;color:#1b354f;margin:0 0 3px}
		.crane-gantt-toolbar p {font-size:12px;color:#657b90;margin:0}
		.crane-gantt-controls {margin:0}.crane-gantt-controls label {font-size:11px;font-weight:600;color:#657b90;margin:0}
		.crane-gantt-controls input,.crane-gantt-controls select {border-radius:8px!important}
		.crane-gantt-legend {margin:0 0 11px;font-size:11px;color:#657b90;gap:15px}
		.crane-gantt-legend i {border-radius:6px;vertical-align:middle}
		.crane-gantt-detail {display:none;position:relative;background:#f2faf9;border:1px solid #cce5e1;border-radius:10px;padding:12px 16px;margin-bottom:12px;font-size:12px;line-height:1.6;color:#25485b}
		.crane-gantt-detail.show {display:block}.crane-gantt-detail strong {font-size:13px;color:#1b354f}.crane-gantt-detail a {font-weight:600}
		.crane-gantt-detail-close {position:absolute;right:12px;top:7px;border:0;background:transparent;font-size:20px;color:#738b94}
		.crane-gantt-scroll {max-height:calc(100vh - 360px);min-height:170px;border-color:#dce7ee;border-radius:13px;box-shadow:0 7px 22px rgba(32,64,96,.04)}
		.crane-gantt-row {border-color:#e8eff4;min-height:67px}.crane-gantt-row.header {background:#f5f8fb;min-height:55px}
		.crane-gantt-label {width:235px;min-width:235px;padding:13px 15px;border-color:#dce7ee;font-size:13px;font-weight:700;color:#1b354f}
		.crane-gantt-row.header .crane-gantt-label {background:#f5f8fb;font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#657b90}
		.crane-gantt-label small {margin-top:5px;font-size:11px;font-weight:400;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
		.crane-gantt-track {background:repeating-linear-gradient(to right,transparent 0,transparent calc(var(--day-width) - 1px),#eef3f6 calc(var(--day-width) - 1px),#eef3f6 var(--day-width))}
		.crane-gantt-month {top:7px;color:#254157;font-size:11px}.crane-gantt-tick {top:31px;font-size:10px}
		.crane-gantt-bar {height:17px;border-radius:5px;box-shadow:0 2px 5px rgba(32,72,110,.14);transition:filter .15s,transform .15s}
		.crane-gantt-bar:hover,.crane-gantt-dot:hover {filter:brightness(.93);transform:translateY(-1px)}
		.crane-gantt-bar.planned.reserved {background:linear-gradient(90deg,#4d83df,#70a1ee);opacity:1}
		.crane-gantt-bar.planned.draft {background:#d3dfeb;border:1px dashed #8da3b9;box-shadow:none;opacity:1}
		.crane-gantt-bar.planned.cancelled {background:#bdc9d2;box-shadow:none;opacity:.55}
		.crane-gantt-dot {top:auto;width:12px;height:10px;border-radius:5px;background:#27a989;transform:none}
		.crane-gantt-dot.draft {background:#e0a13e}
		.crane-gantt-today {position:absolute;top:0;bottom:0;width:2px;background:#eeab51;z-index:1;pointer-events:none}
		.crane-gantt-weekend {position:absolute;top:0;bottom:0;background:rgba(204,220,231,.22);pointer-events:none}
		@media(max-width:900px){.crane-gantt-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.crane-gantt-label{width:180px;min-width:180px}}
	</style><div class="crane-gantt-hero"></div><div class="crane-gantt-cards"></div><div class="crane-gantt-toolbar"><div><h3>${__("Fleet timeline")}</h3><p class="crane-gantt-caption"></p></div><div class="crane-gantt-controls"></div></div><div class="crane-gantt-legend"></div><div class="crane-gantt-detail"></div><div class="crane-gantt-scroll"></div>`);
	const $controls = page.main.find(".crane-gantt-controls");
	const $scroll = page.main.find(".crane-gantt-scroll");
	const $legend = page.main.find(".crane-gantt-legend");
	const $detail = page.main.find(".crane-gantt-detail");
	$controls.html(`<label>${__("Zoom")}
		<select class="form-control input-sm crane-gantt-zoom">
			<option>Day</option><option>Week</option><option>Month</option>
		</select></label><input class="form-control input-sm crane-gantt-search" placeholder="${__("Find crane")}">`);
	$legend.html(`<span><i style="background:#5b8def"></i>${__("Reserved")}</span>
		<span><i style="background:#d3dfeb;border:1px dashed #8da3b9"></i>${__("Draft / cancelled")}</span>
		<span><i style="background:#27a989"></i>${__("Work recorded")}</span>
		<span><i style="background:#eeab51"></i>${__("Today")}</span>`);
	$controls.on("change", ".crane-gantt-zoom", (event) => {
		state.zoom = event.currentTarget.value;
		render();
	});
	$controls.on("input", ".crane-gantt-search", (event) => {
		state.search = event.currentTarget.value.toLowerCase();
		render();
	});
	$scroll.on("click", ".crane-gantt-bar", (event) => {
		const { assignment, row } = event.currentTarget.dataset;
		const segment = (state.data.cranes || []).flatMap((lane) => lane.segments)
			.find((item) => item.assignment === assignment && item.row_name === row);
		if (!segment) return;
		show_detail(`<strong>${escape(segment.row_status)} · ${escape(assignment)}</strong><br>
			${escape(segment.start_date)} – ${escape(segment.end_date)}<br>
			<a href="/app/crane-assignment/${encodeURIComponent(assignment)}">${__("Open assignment")}</a>`);
	});
	$scroll.on("click", ".crane-gantt-dot", (event) => {
		const crane = event.currentTarget.dataset.crane;
		const date = event.currentTarget.dataset.date;
		const lane = (state.data.cranes || []).find((item) => item.crane === crane);
		const marker = lane && lane.work.find((item) => item.date === date);
		if (!marker) return;
		const links = marker.timesheets.map((name) =>
			`<a href="/app/crane-timesheet/${encodeURIComponent(name)}">${escape(name)}</a>`
		).join(" · ");
		show_detail(`<strong>${escape(lane.crane_name)} · ${escape(date)}</strong><br>
			${escape(format_hours(marker.crane_hours))} ${__("crane hours")} · ${escape(format_hours(marker.operator_hours))} ${__("driver hours")}<br>
			${escape(marker.statuses.join(", "))} · ${links}`);
	});
	$detail.on("click", ".crane-gantt-detail-close", () => $detail.removeClass("show").empty());
	function show_detail(html) {
		$detail.html(`${html}<button type="button" class="crane-gantt-detail-close" aria-label="${__("Close")}">×</button>`).addClass("show");
	}
	function format_hours(value) {
		return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
	}

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
	function set_dates(from_date, to_date) {
		state.from_date = from_date;
		state.to_date = to_date;
		state.updating_fields = true;
		fields.from_date.set_value(from_date);
		fields.to_date.set_value(to_date);
		state.updating_fields = false;
	}
	async function use_project_dates() {
		if (!state.project) {
			set_dates(frappe.datetime.add_days(frappe.datetime.get_today(), -30), frappe.datetime.add_days(frappe.datetime.get_today(), 90));
			return;
		}
		const project = state.project;
		const { message } = await frappe.db.get_value("Crane Project", project, ["expected_start_date", "expected_end_date"]);
		if (state.project === project && message) set_dates(message.expected_start_date, message.expected_end_date);
	}
	function choose_zoom() {
		if (!state.from_date || !state.to_date) return;
		const days = days_between(state.from_date, state.to_date);
		state.zoom = days > 180 ? "Month" : days > 45 ? "Week" : "Day";
		$controls.find(".crane-gantt-zoom").val(state.zoom);
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
				assignment: state.assignment,
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
		const width = { Day: 30, Week: 14, Month: 5 }[state.zoom];
		const track_width = Math.max(days * width, 760);
		const lanes = state.data.cranes.filter((item) =>
			(item.crane + " " + item.crane_name).toLowerCase().includes(state.search)
		);
		const segments = lanes.flatMap((lane) => lane.segments);
		const work = lanes.flatMap((lane) => lane.work);
		const total_hours = work.reduce((sum, marker) => sum + Number(marker.crane_hours || 0), 0);
		const drafts = segments.filter((segment) => segment.row_status === "Draft").length;
		const title = state.assignment || state.project || __("Crane reservations");
		page.main.find(".crane-gantt-hero").html(`<div class="crane-gantt-eyebrow">${
			state.assignment ? __("Assignment schedule") : state.project ? __("Project schedule") : __("Fleet overview")
		}</div><h2>${escape(title)}</h2><p>${escape(from_date)} — ${escape(to_date)} · ${__("Bookings and recorded work in one timeline.")}</p>`);
		page.main.find(".crane-gantt-cards").html([
			[lanes.length, __("Cranes shown"), ""],
			[segments.filter((segment) => segment.row_status === "Reserved").length, __("Booked periods"), ""],
			[format_hours(total_hours), __("Recorded crane hours"), "work"],
			[drafts, __("Draft allocations"), "due"],
		].map(([value, label, style]) => `<div class="crane-gantt-card ${style}"><strong>${escape(value)}</strong><span>${escape(label)}</span></div>`).join(""));
		page.main.find(".crane-gantt-caption").text(state.assignment ? __("Only this assignment") : state.project ? __("Grouped by crane in this project") : __("Grouped by crane across visible projects"));
		$detail.removeClass("show").empty();
		if (!lanes.length) {
			$scroll.html(
				`<div class="crane-gantt-empty">${__("No reservations or work match these filters.")}</div>`
			);
			return;
		}
		const today_offset = days_between(from_date, frappe.datetime.get_today());
		function decorations() {
			const result = [];
			if (state.zoom === "Day") for (let i = 0; i < days; i++) {
				if ([0, 6].includes(day(date_at(from_date, i)).getUTCDay()))
					result.push(`<span class="crane-gantt-weekend" style="left:${i * width}px;width:${width}px"></span>`);
			}
			if (today_offset >= 0 && today_offset < days)
				result.push(`<span class="crane-gantt-today" style="left:${(today_offset + .5) * width}px" title="${__("Today")}"></span>`);
			return result.join("");
		}
		const header = [];
		for (let i = 0; i < days; i++) {
			const date = date_at(from_date, i);
			const label = day(date);
			if (i === 0 || label.getUTCDate() === 1) {
				header.push(
					`<span class="crane-gantt-month" style="left:${i * width + 5}px">${escape(
						label.toLocaleString(undefined, {
							month: "long",
							year: "numeric",
							timeZone: "UTC",
						})
					)}</span>`
				);
			}
			if (i === 0 || i % (state.zoom === "Day" ? 7 : state.zoom === "Week" ? 14 : 30) === 0) {
				header.push(
					`<span class="crane-gantt-tick" style="left:${i * width + 5}px">${escape(label.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" }))}</span>`
				);
			}
		}
		const html = [
			`<div class="crane-gantt-row header"><div class="crane-gantt-label">${__(
				"Crane / activity"
			)}</div><div class="crane-gantt-track" style="width:${track_width}px;--day-width:${width}px">${decorations()}${header.join(
				""
			)}</div></div>`,
		];
		for (const lane of lanes) {
			const parts = [decorations()];
			let segment_index = 0;
			const row_height = Math.max(67, lane.segments.length * 27 + 32);
			const work_top = row_height - 20;
			function bar(start, end, css, segment, title) {
				if (!start || !end || end < from_date || start > to_date) return;
				const left = Math.max(0, days_between(from_date, start)) * width + 3;
				const right = Math.min(days - 1, days_between(from_date, end));
				const bar_width = Math.max(
					3,
					(right - Math.max(0, days_between(from_date, start)) + 1) * width - 6
				);
				parts.push(`<button type="button" class="crane-gantt-bar ${css}" style="left:${left}px;width:${bar_width}px;top:${segment_index * 27 + 11}px"
					title="${escape(title)}" data-assignment="${escape(segment.assignment)}" data-row="${escape(segment.row_name)}"></button>`);
			}
			for (const segment of lane.segments) {
				const id = `${segment.project} · ${segment.assignment} · ${segment.row_status}`;
				bar(
					segment.start_date,
					segment.end_date,
					"planned " + segment.row_status.toLowerCase().replaceAll(" ", "-"),
					segment,
					`${id}: ${segment.start_date} – ${segment.end_date}`
				);
				segment_index++;
			}
			for (const marker of lane.work) {
				const offset = days_between(from_date, marker.date);
				if (offset < 0 || offset >= days) continue;
				const draft = marker.statuses.includes("Draft");
				const title = `${marker.date} | ${format_hours(marker.crane_hours)} ${__("crane hours")} | ${marker.statuses.join(", ")}`;
				parts.push(`<button type="button" class="crane-gantt-dot${
					draft ? " draft" : ""
				}" style="left:${offset * width + 5}px;width:${Math.max(8, width - 10)}px;top:${work_top}px"
					title="${escape(title)}" data-crane="${escape(lane.crane)}" data-date="${escape(marker.date)}"></button>`);
			}
			const lane_hours = lane.work.reduce((sum, marker) => sum + Number(marker.crane_hours || 0), 0);
			const lane_caption = state.project
				? `${lane.segments.length} ${__("allocations")} · ${format_hours(lane_hours)} ${__("crane hours")}`
				: [...new Set(lane.segments.map((segment) => segment.project))].join(" · ") || __("Work recorded");
			html.push(`<div class="crane-gantt-row" style="height:${row_height}px"><div class="crane-gantt-label">${escape(
				lane.crane_name
			)}<small title="${escape(lane_caption)}">${escape(lane_caption)}</small></div>
				<div class="crane-gantt-track" style="width:${track_width}px;height:${row_height}px;--day-width:${width}px">${parts.join("")}</div></div>`);
		}
		$scroll.html(html.join(""));
	}

	frappe.pages["crane-project-gantt"].on_page_show = async () => {
		const route = frappe.get_route();
		const options = frappe.route_options || {};
		frappe.route_options = null;
		state.updating_fields = true;
		state.project = route[1] || options.project || "";
		state.assignment = options.assignment || null;
		state.crane = options.crane || null;
		fields.project.set_value(state.project);
		fields.crane.set_value(state.crane);
		state.updating_fields = false;
		if (options.from_date && options.to_date) set_dates(options.from_date, options.to_date);
		else await use_project_dates();
		choose_zoom();
		load();
	};
};
