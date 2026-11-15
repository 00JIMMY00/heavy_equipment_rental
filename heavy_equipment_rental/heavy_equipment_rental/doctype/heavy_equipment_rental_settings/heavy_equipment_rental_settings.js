frappe.ui.form.on('Heavy Equipment Rental Settings', {
    setup(frm) {
        const company_for = (cdt, cdn) => locals[cdt][cdn].company;
        frm.set_query('expense_account', 'repair_defaults', (doc, cdt, cdn) => ({filters: {
            company: company_for(cdt, cdn), root_type: 'Expense', is_group: 0, disabled: 0
        }}));
        frm.set_query('warehouse', 'repair_defaults', (doc, cdt, cdn) => ({filters: {
            company: company_for(cdt, cdn), is_group: 0, disabled: 0
        }}));
        frm.set_query('mode_of_payment', 'repair_defaults', () => ({filters: {enabled: 1}}));
    },
});
