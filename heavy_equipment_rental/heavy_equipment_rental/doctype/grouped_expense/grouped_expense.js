const her_expense_api = 'heavy_equipment_rental.consolidated_expenses.';
frappe.ui.form.on('Grouped Expense', {
    setup(frm) {
        frm.set_query('expense_entry_type', 'items', () => ({filters: {company: frm.doc.company, enabled: 1}}));
        frm.set_query('mode_of_payment', () => ({filters: {enabled: 1}}));
        frm.set_query('mode_of_payment', 'items', () => ({filters: {enabled: 1}}));
        frm.set_query('employee', () => ({filters: {company: frm.doc.company}}));
        frm.set_query('cost_center', () => ({filters: {company: frm.doc.company, is_group: 0, disabled: 0}}));
        frm.set_query('crane_assignment', () => ({filters: {company: frm.doc.company}}));
        frm.set_query('crane', () => frm.doc.crane_assignment ? {
            query: 'heavy_equipment_rental.rental_expenses.assignment_cranes',
            filters: {assignment: frm.doc.crane_assignment}
        } : {});
        frm.set_query('crane_timesheet', () => ({filters: {crane: frm.doc.crane, docstatus: ['<', 2]}}));
    },
    async refresh(frm) {
        const salary = Boolean(frm.doc.timesheet_salary_payment);
        for (const field of ['company', 'employee', 'crane', 'crane_timesheet']) frm.set_df_property(field, 'read_only', salary);
        const items_grid = frm.fields_dict.items.grid;
        for (const field of ['expense_entry_type', 'mode_of_payment']) {
            items_grid.update_docfield_property(field, 'read_only', salary);
        }
        frm.set_df_property('mode_of_payment', 'label', salary ? __('Mode of Payment') : __('Default Mode of Payment'));
        if (frm.doc.docstatus > 0) {
            frm.add_custom_button(__("Accounting Ledger"), () => {
                const dates = (frm.doc.items || []).map(row => row.posting_date).filter(Boolean).sort();
                frappe.set_route("query-report", "General Ledger", {
                    company: frm.doc.company, consolidated_expense: frm.doc.name,
                    from_date: dates[0], to_date: dates[dates.length - 1],
                    show_cancelled_entries: frm.doc.docstatus === 2 ? 1 : 0,
                });
            }, __("View"));
        }
        if (frm.doc.docstatus !== 0) return;
        await frm.trigger('load_defaults');
        const grid = frm.fields_dict.items.grid;
        const bind = (selector, label, action) => grid.wrapper.find(selector).removeClass('hidden').text(__(label)).off('click').on('click', action);
        bind('.grid-download', 'Download Excel Template', () => {
            window.open('/api/method/' + her_expense_api + 'download_template');
        });
        bind('.grid-upload', 'Upload Excel Template', () => {
            if (!frm.doc.company) return frappe.msgprint(__('Select a Company first.'));
            const company = frm.doc.company;
            new frappe.ui.FileUploader({
                allow_multiple: false, make_attachments_public: false,
                restrictions: {allowed_file_types: ['.xlsx'], max_file_size: 2 * 1024 * 1024},
                on_success: async file => {
                    const rows = await frappe.xcall(her_expense_api + 'upload_template', {file_url: file.file_url, company});
                    if (frm.doc.company !== company || frm.doc.docstatus !== 0) return;
                    const defaults = frm.her_expense_defaults || {};
                    const normalized = rows.map(values => ({...values,
                        expense_entry_type: values.expense_entry_type || defaults.expense_type,
                        mode_of_payment: values.mode_of_payment || frm.doc.mode_of_payment}));
                    const key = row => JSON.stringify([row.posting_date, (row.description || '').trim(),
                        flt(row.amount), row.expense_entry_type || defaults.expense_type,
                        row.mode_of_payment || frm.doc.mode_of_payment]);
                    const seen = new Set((frm.doc.items || []).map(key));
                    const fresh = normalized.filter(row => {
                        const value = key(row);
                        if (seen.has(value)) return false;
                        seen.add(value); return true;
                    });
                    const proceed = await new Promise(resolve => frappe.confirm(
                        __('Append {0} rows and skip {1} identical rows? Existing rows will not be changed.',
                            [fresh.length, rows.length - fresh.length]), () => resolve(true), () => resolve(false)));
                    if (!proceed || frm.doc.company !== company || frm.doc.docstatus !== 0) return;
                    fresh.forEach(values => frm.add_child('items', values));
                    frm.refresh_field('items');
                    frm.dirty();
                    frm.trigger('calculate_total');
                    frappe.show_alert({message: __('Added {0} rows. Review and save before submitting.', [fresh.length]), indicator: 'green'});
                }
            });
        });
    },
    async load_defaults(frm) {
        if (!frm.doc.company || frm.doc.timesheet_salary_payment) return;
        const company = frm.doc.company;
        const defaults = await frappe.xcall(her_expense_api + 'get_defaults', {company});
        if (company !== frm.doc.company) return;
        frm.her_expense_defaults = defaults;
        if (!frm.doc.mode_of_payment && defaults.mode_of_payment) await frm.set_value('mode_of_payment', defaults.mode_of_payment);
        for (const row of frm.doc.items || []) {
            if (!row.expense_entry_type && defaults.expense_type) await frappe.model.set_value(row.doctype, row.name, 'expense_entry_type', defaults.expense_type);
            if (!row.mode_of_payment && frm.doc.mode_of_payment) await frappe.model.set_value(row.doctype, row.name, 'mode_of_payment', frm.doc.mode_of_payment);
        }
    },
    async company(frm) {
        if (frm.doc.timesheet_salary_payment) return;
        frm.her_expense_defaults = {};
        await frm.set_value({mode_of_payment: null, cost_center: null, employee: null});
        for (const row of frm.doc.items || []) {
            await frappe.model.set_value(row.doctype, row.name, {expense_entry_type: null, mode_of_payment: null});
        }
        await frm.trigger('load_defaults');
    },
    crane(frm) { if (!frm.doc.timesheet_salary_payment) frm.set_value({crane_timesheet: null, profit_settlement: null}); },
    async crane_timesheet(frm) {
        if (!frm.doc.crane_timesheet) return frm.set_value({crane_assignment: null, profit_settlement: null});
        const name = frm.doc.crane_timesheet;
        const {message: sheet} = await frappe.db.get_value('Crane Timesheet', name, ['assignment', 'profit_settlement']);
        if (name === frm.doc.crane_timesheet) frm.set_value({crane_assignment: sheet.assignment, profit_settlement: sheet.profit_settlement});
    },
    mode_of_payment(frm) {
        for (const row of frm.doc.items || []) {
            if (frm.doc.timesheet_salary_payment || !row.mode_of_payment) frappe.model.set_value(row.doctype, row.name, 'mode_of_payment', frm.doc.mode_of_payment);
        }
    },
    calculate_total(frm) { frm.set_value('total', (frm.doc.items || []).reduce((sum, row) => sum + flt(row.amount), 0)); }
});
frappe.ui.form.on('Grouped Expense Item', {
    items_add(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, {
            posting_date: frappe.datetime.get_today(),
            expense_entry_type: (frm.her_expense_defaults || {}).expense_type,
            mode_of_payment: frm.doc.mode_of_payment,
        });
    },
    amount(frm) { frm.trigger('calculate_total'); },
    items_remove(frm) { frm.trigger('calculate_total'); }
});
