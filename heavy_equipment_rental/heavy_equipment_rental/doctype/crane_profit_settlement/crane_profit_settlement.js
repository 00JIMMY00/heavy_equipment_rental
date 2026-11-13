frappe.ui.form.on("Crane Profit Settlement", {
    async timesheet(frm) {
        if (!frm.doc.timesheet || frm.doc.docstatus !== 0) return;
        const sheet = frm.doc.timesheet;
        const { message } = await frappe.db.get_value("Crane Timesheet", sheet,
            ["crane", "period_start", "period_end", "sales_invoice"]);
        if (frm.doc.timesheet === sheet && message) await frm.set_value({ crane: message.crane,
            from_date: message.period_start, to_date: message.period_end, sales_invoice: message.sales_invoice });
    },
    async crane(frm) {
        if (!frm.is_new() || !frm.doc.crane || frm.doc.timesheet) return;
        const crane = frm.doc.crane;
        const request = frm._defaults_request = (frm._defaults_request || 0) + 1;
        const start = frm.doc.from_date;
        const end = frm.doc.to_date;
        const { message } = await frappe.call({
            method: "heavy_equipment_rental.profit_sharing.settlement_defaults", args: { crane },
        });
        if (crane !== frm.doc.crane || request !== frm._defaults_request) return;
        const values = { company: message.company };
        if (frm.doc.from_date === start) values.from_date = message.from_date;
        if (frm.doc.to_date === end) values.to_date = message.to_date;
        frm.set_value(values);
    },
    refresh(frm) {
        if (!frm.is_new()) render_partner_payments(frm);
        frm.set_df_property("crane", "read_only", Boolean(frm.doc.timesheet));
        const sources = JSON.parse(frm.doc.source_snapshot || "[]");
        const grouped = new Map();
        for (const source of sources) {
            const key = JSON.stringify([source.doctype, source.name]);
            const row = grouped.get(key) || { ...source, revenue: 0, expenses: 0, income_accounts: new Set() };
            row.revenue += source.revenue || 0;
            row.expenses += source.expenses || 0;
            if (source.income_account) row.income_accounts.add(source.income_account);
            grouped.set(key, row);
        }
        const esc = value => frappe.utils.escape_html(String(value ?? ""));
        const rows = [...grouped.values()].map(row => `<tr>
            <td>${esc(row.posting_date)}</td>
            <td>${esc(row.rental_assignment || "")}</td>
            <td>${row.service_from_date ? `${esc(row.service_from_date)} → ${esc(row.service_to_date)}` : ""}</td>
            <td>${esc(__(row.doctype))}</td>
            <td><a href="/app/${encodeURIComponent(frappe.router.slug(row.doctype))}/${encodeURIComponent(row.name)}">${esc(row.name)}</a></td>
            <td>${[...row.income_accounts].map(account => `<a href="/app/account/${encodeURIComponent(account)}">${esc(account)}</a>`).join("<br>")}</td>
            <td class="text-right">${format_currency(row.revenue, frm.doc.currency)}</td>
            <td class="text-right">${format_currency(row.expenses, frm.doc.currency)}</td></tr>`).join("");
        frm.fields_dict.source_details.$wrapper.html(rows
            ? `<div class="table-responsive"><table class="table table-bordered"><thead><tr>
                ${["Posting Date", "Crane Assignment", "Service Period", "Document Type", "Document", "Revenue Account", "Revenue", "Operating Expenses"].map(label => `<th>${esc(__(label))}</th>`).join("")}
                </tr></thead><tbody>${rows}</tbody></table></div>`
            : `<p class="text-muted">${__("No posted revenue or costs in this period.")}</p>`);
        frm.set_intro(__("Save to calculate: allocated invoice Grand Total, less operating share, less expenses, then distribute the remaining balance. A deficit stops the settlement. Submit to close the period and create partner payables. Historical agreements retain their original revenue basis."));
        if (frm.doc.timesheet && frm.doc.settlement_basis === "Timesheet") {
            frm.set_df_property("from_date", "read_only", 1);
            frm.set_df_property("to_date", "read_only", 1);
            frm.set_intro(__("Partner entitlements are posted automatically when the linked Sales Invoice is submitted. Use Partner Payment to pay the outstanding balance."), "blue");
        }
        const agreement = JSON.parse(frm.doc.agreement_snapshot || "{}");
        if (agreement.posting_basis === "Source Revenue Accounts") {
            frm.set_intro(__("Partner entitlements reduce the revenue accounts of the source documents. Cash or bank payment is recorded separately through Partner Payment."), "blue");
        }
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button(__("Recalculate"), () => frm.save());
        }
        if (frm.doc.docstatus !== 1 || !frm.doc.journal_entry || !frappe.model.can_create("Payment Entry")) return;
        frm.add_custom_button(__("Partner Payment"), () => {
            return frappe.call({
                method: "heavy_equipment_rental.partner_reporting.settlement_payment_details",
                args: { settlement: frm.doc.name },
            }).then(({ message }) => {
                const partners = message.balances.filter(r => r.outstanding_amount > 0);
                const create = async partner => {
                    const { message: payment_doc } = await frappe.call({
                        method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.crane_profit_settlement.make_partner_payment",
                        args: { settlement: frm.doc.name,
                            shareholder: partner.party_type === "Shareholder" ? partner.party : undefined,
                            supplier: partner.party_type === "Supplier" ? partner.party : undefined }, freeze: true,
                    });
                    const [payment] = frappe.model.sync(payment_doc);
                    frappe.set_route("Form", payment.doctype, payment.name);
                };
                if (!partners.length) return frappe.msgprint(__("All partner entitlements are paid."));
                if (partners.length === 1) return create(partners[0]);
                frappe.prompt([{
                    fieldname: "partner", fieldtype: "Select", label: __("Partner"), reqd: 1,
                    options: partners.map((r, index) => ({ value: String(index),
                        label: `${r.partner_name} · ${format_currency(r.outstanding_amount, frm.doc.currency)}` })),
                }], values => create(partners[Number(values.partner)]), __("Partner Payment"), __("Create Payment"));
            });
        }, __("Create"));
        frm.add_custom_button(__("General Ledger"), () => frappe.set_route("query-report", "General Ledger", {
            company: frm.doc.company, voucher_no: frm.doc.journal_entry,
            from_date: frm.doc.posting_date, to_date: frappe.datetime.get_today(),
        }), __("View"));
    },
});

async function render_partner_payments(frm) {
    if (!frappe.model.can_read("Payment Entry")) return;
    const { message } = await frappe.call({ method: "heavy_equipment_rental.partner_reporting.settlement_payment_details",
        args: { settlement: frm.doc.name } });
    if (!message || frm.doc.name !== cur_frm?.doc.name) return;
    const esc = value => frappe.utils.escape_html(String(value ?? ""));
    const money = value => format_currency(value || 0, frm.doc.currency);
    const table = (headers, rows) => `<div class="table-responsive"><table class="table table-bordered">
        <thead><tr>${headers.map(h => `<th>${esc(__(h))}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
    const balances = message.balances.map(r => `<tr><td>${esc(r.partner_name)}</td>
        <td>${money(r.entitlement)}</td><td>${money(r.pending_entitlement)}</td><td>${money(r.paid_amount)}</td>
        <td>${money(r.outstanding_amount)}</td><td>${esc(__(r.status))}</td></tr>`).join("");
    const payments = message.payments.map(r => `<tr>
        <td><a href="/app/payment-entry/${encodeURIComponent(r.name)}">${esc(r.name)}</a></td>
        <td>${esc(r.posting_date)}</td><td>${esc(r.party_name || r.party)}</td><td>${money(r.amount)}</td>
        <td>${esc(__(r.docstatus === 1 ? "Submitted" : "Draft"))}</td></tr>`).join("");
    frm.fields_dict.partner_payments.$wrapper.html(
        table(["Partner", "Posted Entitlement", "Pending Entitlement", "Paid / Adjusted", "Outstanding", "Entitlement Status"], balances) +
        (payments ? table(["Payment Entry", "Posting Date", "Partner", "Allocated Amount", "Status"], payments) : ""));
}
