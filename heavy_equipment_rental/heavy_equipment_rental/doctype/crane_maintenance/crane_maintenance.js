frappe.ui.form.on("Crane Maintenance", {
	setup(frm) {
		frm.set_query("mode_of_payment", () => ({ filters: { enabled: 1 } }));
	},
	refresh(frm) {
        maintenance_rental_context(frm, "setup");
        render_repair_documents(frm);
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
        wrapper.text(__(is_auto_repair(frm) ? "Enter the repair items, save, then use Submit." : "Save this repair to create its stock and accounting documents."));
        return;
    }
    if (frm.doc.docstatus === 0 && !is_auto_repair(frm)) {
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
            : `<p class="text-muted">${esc(__(is_auto_repair(frm) ? "No postings yet. Enter the repair items, save, then use Submit." : "No stock or accounting documents yet. Create the appropriate document, review it and submit before submitting Maintenance."))}</p>`);
    } catch (error) {
        if (request === frm._repair_request) wrapper.text(__("Accounting document read permission is required to review repair postings."));
    }
}

frappe.ui.form.on("Crane Maintenance", {
    cost_treatment(frm) {
        update_cost_treatment_description(frm);
        if (!['Operating Expense', 'Capitalize Improvement'].includes(frm.doc.cost_treatment) && frm.doc.repair_source) frm.set_value('repair_source', 'Manual Documents');
        frm.refresh();
    },
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

frappe.ui.form.on('Crane Maintenance', {
    onload(frm) {
        if (frm.is_new() && frm.doc.amended_from) {
            for (const field of ['repair_purchase_invoice', 'repair_material_issue', 'repair_payment_entry', 'expense_entry', 'legacy_lifecycle']) frm.doc[field] = null;
            frm.doc.status = 'Planned';
            frm.refresh_fields();
        }
        if (frm.is_new() && frm.doc.company) set_repair_company_defaults(frm);
        if (frm.is_new() && ['Operating Expense', 'Capitalize Improvement'].includes(frm.doc.cost_treatment) && !is_auto_repair(frm)) {
            frm.set_value('repair_source', 'My Stock');
        }
        frm.set_query('repair_expense_account', () => ({filters: {
            company: frm.doc.company, root_type: 'Expense', is_group: 0, disabled: 0
        }}));
        frm.set_query('repair_cost_center', () => ({filters: {
            company: frm.doc.company, is_group: 0, disabled: 0
        }}));
        frm.set_query('warehouse', 'repair_items', () => ({filters: {
            company: frm.doc.company, is_group: 0, disabled: 0
        }}));
        frm.set_query('item_code', 'repair_items', () => ({filters: {
            disabled: 0, is_fixed_asset: 0, is_stock_item: frm.doc.repair_source === 'External Service' ? 0 : 1,
            has_serial_no: 0, has_batch_no: 0
        }}));
    },
    refresh(frm) {
        update_cost_treatment_description(frm);
        const automatic = is_auto_repair(frm);
        const locked = !!(frm.doc.docstatus || frm.doc.repair_purchase_invoice || frm.doc.repair_material_issue || ['Completed', 'Cancelled'].includes(frm.doc.status));
        for (const field of ['repair_source', 'repair_supplier', 'supplier_invoice_no',
            'supplier_invoice_date', 'repair_cost_center', 'repair_items', 'supplier_paid_amount', 'mode_of_payment']) {
            frm.set_df_property(field, 'read_only', locked ? 1 : 0);
        }
        frm.fields_dict.repair_items.grid.toggle_display('rate', frm.doc.repair_source !== 'My Stock');
        frm.fields_dict.repair_items.grid.toggle_display('warehouse', frm.doc.repair_source === 'My Stock');
        frm.set_df_property('cost_treatment', 'options', automatic
            ? 'Operating Expense\nCapitalize Improvement'
            : 'Cash Expense\nOperating Expense\nCapitalize Improvement\nRecover from Owner\nNo Cost');
        frm.set_df_property('status', 'options', !frm.doc.docstatus
            ? 'Planned\nIn Progress' : 'Planned\nIn Progress\nCompleted\nCancelled');
        frm.set_df_property('status', 'read_only', frm.doc.docstatus ? 1 : 0);
        frm.set_df_property('cost_treatment', 'hidden', 0);
        frm.set_df_property('cost_treatment', 'read_only', locked ? 1 : 0);
        frm.set_df_property('advanced_repair_section', 'hidden', automatic ? 1 : 0);

    },
    supplier_paid_amount(frm) {
        if (!frm._defaulting_payment) frm.set_value('pay_full_amount', 0);
    },
    async repair_source(frm) {
        if (is_auto_repair(frm) && !['Operating Expense', 'Capitalize Improvement'].includes(frm.doc.cost_treatment)) {
            await frm.set_value('cost_treatment', 'Operating Expense');
        }
        if (is_auto_repair(frm) && !frm.doc.repair_expense_account) set_repair_company_defaults(frm);
        frm.refresh();
    },
    async company(frm) {
        if (frm.doc.repair_purchase_invoice || frm.doc.repair_material_issue || ['Completed', 'Cancelled'].includes(frm.doc.status)) return;
        await frm.set_value('repair_expense_account', '');
        await frm.set_value('repair_cost_center', '');
        await set_repair_company_defaults(frm);
    },
});

async function set_repair_company_defaults(frm) {
    if (!is_auto_repair(frm) || !frm.doc.company || frm.doc.repair_purchase_invoice || frm.doc.repair_material_issue ||
        ['Completed', 'Cancelled'].includes(frm.doc.status)) return;
    const company = frm.doc.company;
    const {message} = await frappe.call({method: 'heavy_equipment_rental.maintenance_posting.get_repair_defaults', args: {company}});
    if (frm.doc.company !== company || !message) return;
    if (!frm.doc.repair_expense_account) await frm.set_value('repair_expense_account', message.expense_account);
    if (!frm.doc.repair_cost_center) await frm.set_value('repair_cost_center', message.cost_center);
    if (!frm.doc.mode_of_payment && message.mode_of_payment) await frm.set_value('mode_of_payment', message.mode_of_payment);
}

function is_auto_repair(frm) {
    return !!frm.doc.repair_source && frm.doc.repair_source !== 'Manual Documents';
}

async function update_repair_payment_total(frm) {
    if (!frm.doc.pay_full_amount || !['External Parts', 'External Service'].includes(frm.doc.repair_source)) return;
    const total = (frm.doc.repair_items || []).reduce((sum, row) => sum + flt(row.qty) * flt(row.rate), 0);
    frm._defaulting_payment = true;
    try { await frm.set_value('supplier_paid_amount', total); }
    finally { frm._defaulting_payment = false; }
}

frappe.ui.form.on('Crane Maintenance Item', {
    qty: update_repair_payment_total,
    rate: update_repair_payment_total,
    repair_items_remove: update_repair_payment_total,
});

function update_cost_treatment_description(frm) {
    const descriptions = {
        'Operating Expense': __('Use for routine repairs, servicing and replacement parts. The cost is recorded as a repair expense without increasing the crane Asset value.'),
        'Capitalize Improvement': __('Use for a major improvement or replacement that adds future benefit to the crane. The cost is added to the crane Asset automatically when you submit Maintenance. Explain the improvement below.'),
        'Recover from Owner': __('Use when the crane owner must reimburse the repair. Select the owner as a Customer and create a Sales Invoice to bill them.'),
        'Cash Expense': __('Use for a repair paid directly from cash or bank. Enter the Cost, Expense Entry Type and Payment Method; submitting Maintenance creates and submits an Expense Entry.'),
        'No Cost': __('Use for an inspection or maintenance job with no cost to record. No accounting or stock document is required.'),
    };
    let description = descriptions[frm.doc.cost_treatment]
        || __('Choose how this repair is recorded in accounting. Routine repairs use Operating Expense.');
    if (is_auto_repair(frm)) {
        description += ' ' + __('Use Submit to save and post everything from this form.');
    }
    frm.set_df_property('cost_treatment', 'description', description);
}

// Native Cancel button, with the complete reversal scope shown before posting.
frappe.ui.form.on('Crane Maintenance', {
    setup(frm) {
        frm.savecancel = async function(btn, callback, on_error) {
            try {
                const plan = await frappe.xcall('heavy_equipment_rental.maintenance_cancellation.get_plan', {name: frm.doc.name});
                const links = plan.map(row => `<li>${frappe.utils.escape_html(__(row.doctype))}: ${frappe.utils.get_form_link(row.doctype, row.name, true)}</li>`).join('');
                frappe.confirm(__('Cancel Maintenance and reverse these documents?') + `<ul>${links}</ul><p>${__('This reverses accounting, including supplier payments. It does not recover money already paid. Use Amend to correct the repair and submit new entries.')}</p>`, async () => {
                    try {
                        await frappe.call({method: 'heavy_equipment_rental.maintenance_cancellation.cancel_with_plan',
                            args: {name: frm.doc.name, confirmed_plan: JSON.stringify(plan)}, freeze: true});
                        await frm.reload_doc();
                        if (callback) callback();
                        frm.script_manager.trigger('after_cancel');
                    } catch (error) { frm.handle_save_fail(btn, on_error); }
                }, () => frm.handle_save_fail(btn, on_error));
            } catch (error) { frm.handle_save_fail(btn, on_error); }
        };
    },
});
