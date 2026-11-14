frappe.ui.form.on("Payment Entry", {
    refresh: partner_entitlements_button,
    payment_type: partner_entitlements_button,
    party_type: partner_entitlements_button,
    party: partner_entitlements_button,
    paid_to: partner_entitlements_button,
});

function partner_entitlements_button(frm) {
    const label = __("Get Outstanding Partner Entitlements");
    frm.remove_custom_button(label);
    if (frm.doc.docstatus === 0 && frm.doc.payment_type === "Pay"
        && ["Shareholder", "Supplier"].includes(frm.doc.party_type)) {
        frm.add_custom_button(label, () => open_partner_entitlements(frm));
    }
}

function open_partner_entitlements(frm) {
    if (!frm.doc.company || !frm.doc.party || !frm.doc.paid_to) {
        frappe.msgprint(__("Select Company, Partner and Account Paid To first."));
        return;
    }
    const context = () => JSON.stringify([frm.doc.name, frm.doc.company, frm.doc.payment_type,
        frm.doc.party_type, frm.doc.party, frm.doc.paid_to]);
    const original_context = context();
    let request = 0;
    const dialog = new frappe.ui.Dialog({
        title: __("Outstanding Partner Entitlements"),
        size: "extra-large",
        fields: [
            {fieldname: "from_date", fieldtype: "Date", label: __("From Date")},
            {fieldtype: "Column Break"},
            {fieldname: "to_date", fieldtype: "Date", label: __("To Date")},
            {fieldtype: "Section Break"},
            {fieldname: "crane", fieldtype: "Link", options: "Crane", label: __("Crane")},
            {fieldtype: "Column Break"},
            {fieldname: "timesheet", fieldtype: "Link", options: "Crane Timesheet", label: __("Crane Timesheet")},
            {fieldtype: "Column Break"},
            {fieldname: "sales_invoice", fieldtype: "Link", options: "Sales Invoice", label: __("Sales Invoice"),
                get_query: () => ({filters: {company: frm.doc.company, docstatus: 1}})},
            {fieldtype: "Section Break"},
            {fieldname: "fetch", fieldtype: "Button", label: __("Search Entitlements"), click: () => fetch_rows()},
            {fieldname: "entitlements", fieldtype: "Table", cannot_add_rows: true, cannot_delete_rows: true,
                description: __("Select entitlements to add. Partial payments are allocated in reference row order. Dates filter settlement posting dates; balances are current."),
                fields: [
                    {fieldname: "settlement", fieldtype: "Link", options: "Crane Profit Settlement", label: __("Settlement"), in_list_view: 1, read_only: 1, columns: 2},
                    {fieldname: "posting_date", fieldtype: "Date", label: __("Posting Date"), in_list_view: 1, read_only: 1, columns: 2},
                    {fieldname: "sales_invoice", fieldtype: "Link", options: "Sales Invoice", label: __("Sales Invoice"), in_list_view: 1, read_only: 1, columns: 2},
                    {fieldname: "timesheet", fieldtype: "Link", options: "Crane Timesheet", label: __("Crane Timesheet"), in_list_view: 1, read_only: 1, columns: 2},
                    {fieldname: "crane", fieldtype: "Link", options: "Crane", label: __("Crane"), read_only: 1},
                    {fieldname: "outstanding_amount", fieldtype: "Currency", options: "currency", label: __("Outstanding"), in_list_view: 1, read_only: 1, columns: 2},
                    {fieldname: "currency", fieldtype: "Data", hidden: 1},
                ], data: []},
        ],
        primary_action_label: __("Add Selected Entitlements"),
        async primary_action() {
            if (context() !== original_context || frm.doc.docstatus !== 0) {
                frappe.msgprint(__("Payment details changed. Reopen the entitlements selector."));
                return;
            }
            const selected = dialog.fields_dict.entitlements.grid.get_selected_children();
            if (!selected.length) return frappe.msgprint(__("Select at least one entitlement."));
            const existing = new Set((frm.doc.references || []).map(r => `${r.reference_doctype}:${r.reference_name}`));
            let added = 0;
            for (const row of selected) {
                const key = `Journal Entry:${row.reference_name}`;
                if (existing.has(key)) continue;
                frm.add_child("references", {reference_doctype: "Journal Entry", reference_name: row.reference_name,
                    total_amount: row.total_amount, outstanding_amount: row.outstanding_amount,
                    allocated_amount: 0, exchange_rate: row.exchange_rate});
                existing.add(key);
                added++;
            }
            if (!added) return frappe.msgprint(__("The selected entitlements are already in Payment References."));
            // A combined payment has no single settlement/work period at header level.
            await frm.set_value({crane_profit_settlement: null, crane_timesheet: null, crane: null});
            frm.refresh_field("references");
            frappe.flags.allocate_payment_amount = true;
            if (!flt(frm.doc.paid_amount)) {
                const total = (frm.doc.references || []).reduce((sum, row) => sum + flt(row.outstanding_amount), 0);
                const rate = flt(frm.doc.target_exchange_rate) / flt(frm.doc.source_exchange_rate);
                if (Number.isFinite(rate) && rate > 0) await frm.set_value("paid_amount", total * rate);
            }
            await frm.events.allocate_party_amount_against_ref_docs(frm, flt(frm.doc.received_amount), true);
            frm.dirty();
            dialog.hide();
        },
    });
    async function fetch_rows() {
        const version = ++request;
        const values = dialog.get_values();
        if (!values) return;
        dialog.fields_dict.entitlements.df.data = [];
        dialog.fields_dict.entitlements.grid.refresh();
        const {message} = await frappe.call({
            method: "heavy_equipment_rental.partner_payment.get_open_partner_entitlements",
            args: {company: frm.doc.company, party_type: frm.doc.party_type, party: frm.doc.party,
                paid_to: frm.doc.paid_to, from_date: values.from_date, to_date: values.to_date,
                crane: values.crane, timesheet: values.timesheet, sales_invoice: values.sales_invoice},
        });
        if (version !== request || context() !== original_context) return;
        dialog.fields_dict.entitlements.df.data = (message || []).map(row => ({...row, name: row.settlement}));
        dialog.fields_dict.entitlements.grid.refresh();
        if (!message?.length) frappe.show_alert({message: __("No outstanding partner entitlements match these filters."), indicator: "blue"});
    }
    dialog.show();
    fetch_rows();
}
