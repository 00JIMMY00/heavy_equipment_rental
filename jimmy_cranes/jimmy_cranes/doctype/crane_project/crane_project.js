function show_crane_project_invoices(project, rows, submitted_without_invoice = []) {
	const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
	const status = [__("Draft"), __("Submitted"), __("Cancelled")];
	const body = (rows || []).map((row) => {
		const warnings = [];
		if (row.missing_cranes?.length)
			warnings.push(__("Crane Item missing: {0}", [row.missing_cranes.map(esc).join(", ")]));
		if (row.zero_total) warnings.push(__("Zero total — review this invoice"));
		if (row.docstatus === 0 && warnings.length && frappe.model.can_write("Sales Invoice"))
			warnings.push(`<button class="btn btn-xs btn-default rebuild-crane-invoice" data-invoice="${esc(row.name)}">${__("Rebuild Draft Items")}</button>`);
		const sheets = (row.timesheets || []).map((name) =>
			`<a href="/app/crane-timesheet/${encodeURIComponent(name)}">${esc(name)}</a>`
		).join(", ");
		return `<tr><td><a href="/app/sales-invoice/${encodeURIComponent(row.name)}">${esc(row.name)}</a></td>
			<td>${status[row.docstatus] || esc(row.docstatus)}</td><td>${esc(row.grand_total)} ${esc(row.currency)}</td>
			<td>${sheets}</td><td>${warnings.join("<br>") || "—"}</td></tr>`;
	}).join("");
	const unlinked = submitted_without_invoice.length
		? `<p>${__("Submitted timesheets without an active invoice")}: ${submitted_without_invoice.map(esc).join(", ")}</p>`
		: "";
	const dialog = frappe.msgprint({
		title: __("Crane Project Sales Invoices"),
		clear: true,
		message: `${unlinked}<div class="table-responsive"><table class="table table-bordered">
			<thead><tr><th>${__("Sales Invoice")}</th><th>${__("Status")}</th><th>${__("Total")}</th>
			<th>${__("Crane Timesheets")}</th><th>${__("Review")}</th></tr></thead>
			<tbody>${body || `<tr><td colspan="5">${__("No Sales Invoices found.")}</td></tr>`}</tbody></table></div>`,
		wide: true,
	});
	dialog.msg_area.off("click", ".rebuild-crane-invoice").on("click", ".rebuild-crane-invoice", function () {
		const invoice_name = $(this).data("invoice");
		frappe.hide_msgprint();
		frappe.prompt(
			[{
				fieldname: "reason", fieldtype: "Small Text", label: __("Rebuild Reason"), reqd: 1,
				description: __("Replaces the draft's current items with charges calculated from its linked submitted Crane Timesheets."),
			}],
			(values) => frappe.call({
				method: "jimmy_cranes.billing.rebuild_draft_invoice",
				args: { project, invoice_name, reason: values.reason },
				freeze: true,
				callback: ({ message }) => {
					if (message?.name) frappe.set_route("Form", "Sales Invoice", message.name);
				},
			}),
			__("Rebuild Draft Invoice")
		);
	});
}

function show_project_invoice_connection(frm) {
	const wrapper = frm.fields_dict.connections_invoice_html?.$wrapper;
	if (!wrapper) return;
	wrapper.empty();
	if (frm.is_new() || !frappe.model.can_read("Sales Invoice") || !frappe.model.can_read("Crane Timesheet")) return;
	const button = $('<button type="button" class="btn btn-default btn-sm">')
		.text(__("Sales Invoices"))
		.appendTo(wrapper);
	button.on("click", () => frappe.call({
		method: "jimmy_cranes.billing.project_invoice_summary",
		args: { project: frm.doc.name },
		callback: ({ message }) => show_crane_project_invoices(frm.doc.name, message?.invoices, message?.submitted_without_invoice),
	}));
}

frappe.ui.form.on("Crane Project", {
	refresh(frm) {
		show_project_invoice_connection(frm);
		if (frm.is_new()) return;
		frm.add_custom_button(__("Gantt Chart"), () => {
			frappe.route_options = {
				project: frm.doc.name,
				from_date: frm.doc.expected_start_date,
				to_date: frm.doc.expected_end_date,
			};
			frappe.set_route("crane-project-gantt");
		});
		if (frappe.model.can_create("Sales Invoice"))
			frm.add_custom_button(__("Generate Sales Invoice"), () => frappe.call({
				method: "jimmy_cranes.billing.generate_sales_invoice",
				args: { project: frm.doc.name },
				freeze: true,
				callback: ({ message }) => {
					if (message?.name) frappe.set_route("Form", "Sales Invoice", message.name);
					else if (message?.existing_invoices) show_crane_project_invoices(frm.doc.name, message.existing_invoices);
				},
			}), __("Create"));
		if (frappe.model.can_create("Expense Entry"))
			frm.add_custom_button(__("Expense Entry"), () => frappe.new_doc("Expense Entry", {
				project: frm.doc.name,
			}), __("Create"));
		if (frm.doc.status === "Open" && frm.perm[0]?.write) {
			if (frappe.model.can_create("Crane Assignment"))
				frm.add_custom_button(__("Crane Assignment"), () => frappe.new_doc("Crane Assignment", { project: frm.doc.name }), __("Create"));
			[["Complete Project", "Complete"], ["Cancel Project", "Cancel"]].forEach(([label, action]) =>
				frm.add_custom_button(__(label), () => {
					const run = (reason) => frappe.call({
						method: "jimmy_cranes.rental_operations.project_action",
						args: { project: frm.doc.name, action, reason },
						freeze: true,
						callback: () => frm.reload_doc(),
					});
					if (action === "Cancel")
						frappe.prompt(
							[{ fieldname: "reason", fieldtype: "Small Text", label: __("Cancellation Reason"), reqd: 1 }],
							(values) => run(values.reason),
							__(label)
						);
					else run();
				}, __("Actions"))
			);
		}
		if (["Completed", "Cancelled"].includes(frm.doc.status) && frm.perm[0]?.write)
			frm.add_custom_button(__("Reopen Project"), () => frappe.prompt(
				[{ fieldname: "reason", fieldtype: "Small Text", label: __("Correction Reason"), reqd: 1 }],
				(values) => frappe.call({
					method: "jimmy_cranes.rental_operations.project_action",
					args: { project: frm.doc.name, action: "Reopen", reason: values.reason },
					freeze: true,
					callback: () => frm.reload_doc(),
				}),
				__("Reopen Project")
			), __("Actions"));
		if (!frappe.model.can_read("Crane Assignment")) return;
		frappe.call({ method: "jimmy_cranes.rental_queries.project_overview", args: { project: frm.doc.name } })
			.then(({ message: rows }) => {
				$(frm.dashboard.parent).find(".crane-project-section").remove();
				if (!rows?.length) return;
				const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
				const body = rows.map((row) => `<tr><td>${esc(row.crane_name)}</td><td><a href="/app/crane-assignment/${encodeURIComponent(row.assignment)}">${esc(row.assignment)}</a></td><td>${esc(row.start_date)}</td><td>${esc(row.expected_end_date)}</td><td>${esc(__(row.status))}</td></tr>`).join("");
				const headings = ["Crane Name", "Assignment", "Start", "End", "Status"].map((h) => `<th>${__(h)}</th>`).join("");
				frm.dashboard.add_section(`<div class="table-responsive"><table class="table table-bordered"><thead><tr>${headings}</tr></thead><tbody>${body}</tbody></table></div>`, __("Assigned Cranes"), "crane-project-section");
			});
	},
});
