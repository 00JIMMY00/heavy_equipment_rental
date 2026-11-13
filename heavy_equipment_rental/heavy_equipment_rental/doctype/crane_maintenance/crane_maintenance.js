frappe.ui.form.on("Crane Maintenance", {
	setup(frm) {
		frm.set_query("mode_of_payment", () => ({ filters: { enabled: 1 } }));
	},
	refresh(frm) {
        maintenance_rental_context(frm, "setup");
        render_repair_documents(frm);
		if (frm.is_new()) return;
		if ((!frm.doc.cost_treatment || frm.doc.cost_treatment === "Cash Expense") && frm.doc.status === "Completed" && frm.doc.cost > 0) {
			if (frm.doc.expense_entry) {
				frappe.db.get_value("Expense Entry", frm.doc.expense_entry, "docstatus").then(({ message }) => {
					if (!message || message.docstatus === 2) frm.trigger("add_expense_button");
				});
			} else {
				frm.trigger("add_expense_button");
			}
		}
	},
	add_expense_button(frm) {
			frm.add_custom_button(__("Create Expense"), () => {
				frappe.call({
						method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_maintenance.crane_maintenance.create_expense",
						args: { maintenance: frm.doc.name },
					}).then(({ message }) => {
						frm.reload_doc();
						frappe.set_route("Form", "Expense Entry", message);
					});
			});
	},
});

async function render_repair_documents(frm) {
    const wrapper = frm.fields_dict.accounting_documents?.$wrapper;
    if (!wrapper) return;
    wrapper.empty();
    const actions = {
        "Operating Expense": [["Consume Spare Parts", "Stock Entry"], ["External Repair Service", "Purchase Invoice"]],
        "Capitalize Improvement": [["Asset Improvement", "Asset Repair"], ["External Improvement Service", "Purchase Invoice"]],
        "Recover from Owner": [["Invoice Owner / Consume Parts", "Sales Invoice"]],
    }[frm.doc.cost_treatment] || [];
    if (frm.is_new()) {
        wrapper.text(__("Save this repair to create its stock and accounting documents."));
        return;
    }
    if (frm.doc.status !== "Cancelled") {
        for (const [label, doctype] of actions) {
            if (!frappe.model.can_create(doctype)) continue;
            frm.add_custom_button(__(label), async () => {
                if (frm.is_dirty()) frappe.throw(__("Save maintenance before creating accounting documents."));
                const { message } = await frappe.call({ method: "heavy_equipment_rental.crane_repairs.make_repair_document",
                    args: { maintenance: frm.doc.name, doctype } });
                const [doc] = frappe.model.sync(message);
                frappe.set_route("Form", doc.doctype, doc.name);
            }, __("Create"));
        }
    }
    const name = frm.doc.name;
    const request = frm._repair_request = (frm._repair_request || 0) + 1;
    try {
        const { message: rows } = await frappe.call({ method: "heavy_equipment_rental.crane_repairs.repair_documents", args: { maintenance: name } });
        if (request !== frm._repair_request || name !== frm.doc.name) return;
        const esc = value => frappe.utils.escape_html(String(value || ""));
        wrapper.html(rows.length ? rows.map(row => `<p><a href="/app/${encodeURIComponent(frappe.router.slug(row.doctype))}/${encodeURIComponent(row.name)}">${esc(__(row.doctype))}: ${esc(row.name)}</a> · ${esc(__(['Draft', 'Submitted', 'Cancelled'][row.docstatus]))}</p>`).join("")
            : `<p class="text-muted">${esc(__("No stock or accounting documents yet. Create the appropriate document, review it and submit before completing the repair."))}</p>`);
    } catch (error) {
        if (request === frm._repair_request) wrapper.text(__("Accounting document read permission is required to review repair postings."));
    }
}

frappe.ui.form.on("Crane Maintenance", {
    cost_treatment(frm) { frm.refresh(); },
});


async function maintenance_rental_context(frm, method) {
    if (frm._setting_rental_context) return;
    await frappe.require("/assets/heavy_equipment_rental/js/rental_context.js");
    return heavy_equipment_rental.rental_context[method](frm);
}
frappe.ui.form.on("Crane Maintenance", Object.fromEntries([
    "crane", "actual_start_date", "actual_end_date",
].map(field => [field, frm => maintenance_rental_context(frm, field === "actual_end_date" ? "changed" : "autofill")])));

frappe.ui.form.on("Crane Maintenance", {
    crane_assignment(frm) { return maintenance_rental_context(frm,"assignment_changed"); },
    crane_timesheet(frm) { return maintenance_rental_context(frm,"timesheet_changed"); },
});
