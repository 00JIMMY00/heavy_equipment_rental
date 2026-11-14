function crane_company_share(doc) {
    if (doc.ownership_type === "Owned") return 100;
    if (["Rented", "Operated for Owner"].includes(doc.ownership_type)) return 0;
    const history = JSON.parse(doc.agreement_history || "[]");
    const active = history.filter(v => v.effective_from <= frappe.datetime.get_today()).at(-1);
    const owners = history.length ? (active?.enabled ? active.partners : []) : (doc.ownership_partners || []);
    return owners.filter(r => r.is_company).reduce((sum, row) => sum + flt(row.ownership_percentage), 0);
}

function update_crane_asset_controls(frm) {
    const share = crane_company_share(frm.doc);
    const basis = share ? (frm.doc.ownership_type === "Owned" ? "Company Owned" : "Company Interest Only") : "";
    frm.toggle_display("asset_section", share > 0 || Boolean(frm.doc.asset));
    frm.set_df_property("asset_accounting_basis", "options", "\nCompany Owned\nCompany Interest Only");
    if (frm.doc.asset_accounting_basis !== basis) {
        frm.doc.asset_accounting_basis = basis;
        frm.refresh_field("asset_accounting_basis");
    }
}

function render_crane_operations(frm) {
    const wrapper = frm.fields_dict.operations_hub?.$wrapper;
    if (!wrapper) return;
    wrapper.empty();
    if (frm.is_new()) return;
    const saved = action => {
        if (frm.is_dirty()) frappe.throw(__("Save the Crane before starting another document."));
        return action();
    };
    const company = frm.doc.sharing_company || frappe.defaults.get_user_default("Company");
    const sections = [
        ["Rental Work", [
            ["Book Crane", "Crane Assignment", "create", () => frappe.new_doc("Crane Assignment", { company }, doc => {
                const row = frappe.model.add_child(doc, "Assigned Crane", "assigned_cranes");
                row.crane = frm.doc.name;
            })],
            ["Record Work", "Crane Timesheet", "create", () => frappe.new_doc("Crane Timesheet", { crane: frm.doc.name })],
            ["Timesheets & Invoices", "Crane Timesheet", "read", () => frappe.set_route("List", "Crane Timesheet", { crane: frm.doc.name })],
        ]],
        ["Repairs & Stock", [
            ["New Repair", "Crane Maintenance", "create", () => frappe.new_doc("Crane Maintenance", {
                crane: frm.doc.name, company, cost_treatment: "Operating Expense", actual_start_date: frappe.datetime.get_today(),
            })],
            ["Repair History", "Crane Maintenance", "read", () => frappe.set_route("List", "Crane Maintenance", { crane: frm.doc.name })],
            ["Consumed Parts", "Stock Entry", "read", () => frappe.set_route("List", "Stock Entry", { crane: frm.doc.name })],
        ]],
        ["Asset & Funding", [
            [frm.doc.asset ? "Open Asset" : "Create Asset", "Asset", frm.doc.asset ? "read" : "create", () => frm.doc.asset
                ? frappe.set_route("Form", "Asset", frm.doc.asset)
                : frappe.call({ method: "heavy_equipment_rental.crane_assets.make_company_asset", args: { crane: frm.doc.name } }).then(({message}) => {
                    const [doc] = frappe.model.sync(message);
                    frappe.set_route("Form", doc.doctype, doc.name);
                })],
            ["Capital / Owner Funding", "Journal Entry", "create", () => frappe.new_doc("Journal Entry", { company }, doc => {
                const row = frappe.model.add_child(doc, "Journal Entry Account", "accounts");
                row.crane = frm.doc.name;
            })],
        ]],
        ["Owners & Results", [
            ["Review Settlements", "Crane Profit Settlement", "read", () => frappe.set_route("List", "Crane Profit Settlement", { crane: frm.doc.name })],
            ["Profit Distribution Details", "Crane Profit Settlement", "read", () => frappe.set_route("query-report", "Crane Profit Distribution", { crane: frm.doc.name, company })],
            ["Owner Balances & Payments", "Crane Profit Settlement", "read", () => frappe.set_route("query-report", "Crane Partner Summary", { crane: frm.doc.name, company })],
            ["Rental Profitability", "Sales Invoice", "read", () => frappe.set_route("query-report", "Crane Rental Profitability", { crane: frm.doc.name, company })],
        ]],
    ];
    const esc = value => frappe.utils.escape_html(String(value || ""));
    wrapper.append(`<p class="text-muted">${esc(__("Start work here. ERPNext documents hold stock, Asset values, invoices and payments."))}</p>`);
    const grid = $('<div class="row"></div>').appendTo(wrapper);
    for (const [label, actions] of sections) {
        const available = actions.filter(([, dt, permission]) => (dt !== "Asset" || crane_company_share(frm.doc) > 0) && (permission === "create" ? frappe.model.can_create(dt) : frappe.model.can_read(dt)));
        if (!available.length) continue;
        const box = $('<div class="col-sm-6 mb-3"><div class="border rounded p-3 h-100"></div></div>').appendTo(grid).children();
        box.append(`<h5>${esc(__(label))}</h5>`);
        for (const [title, , , action] of available) {
            $('<button type="button" class="btn btn-default btn-sm mr-2 mb-2"></button>')
                .text(__(title)).on("click", () => saved(action)).appendTo(box);
        }
    }
    if (!frm.doc.asset && crane_company_share(frm.doc) > 0) wrapper.append(`<p class="text-muted">${esc(__("Link the physical Asset in Crane Details after accounting reviews ownership and recognition. Rental prices do not determine asset cost."))}</p>`);
}

frappe.ui.form.on("Crane", {
    setup(frm) {
        frm.set_query("asset", () => ({ filters: {
            docstatus: ["<", 2], asset_quantity: 1,
            status: ["not in", ["Sold", "Scrapped", "Capitalized"]],
            ...(frm.doc.sharing_company ? { company: frm.doc.sharing_company } : {}),
            asset_owner: "Company",
        } }));
        frm.set_query("profit_allocation_account", () => ({ filters: {
            company: frm.doc.sharing_company, is_group: 0, disabled: 0,
            root_type: ["in", ["Expense", "Equity"]],
        } }));
        frm.set_query("partner_payable_account", () => ({ filters: {
            company: frm.doc.sharing_company, is_group: 0, disabled: 0, account_type: "Payable",
        } }));
        frm.set_query("sharing_cost_center", () => ({ filters: {
            company: frm.doc.sharing_company, is_group: 0, disabled: 0,
        } }));
        frm.set_query("operating_shareholder", () => ({ filters: {
            name: ["in", (frm.doc.ownership_partners || []).filter(r => !r.is_company && r.shareholder).map(r => r.shareholder)],
            company: frm.doc.sharing_company,
        } }));
        frm.set_query("shareholder", "ownership_partners", () => ({ filters: { company: frm.doc.sharing_company } }));
    },
    async sharing_company(frm) {
        if (!frm.doc.sharing_company) return;
        const company = frm.doc.sharing_company;
        const { message } = await frappe.call({ method: "heavy_equipment_rental.partner_accounts.agreement_defaults", args: { company } });
        if (frm.doc.sharing_company === company) await frm.set_value(message);
    },
    async ownership_type(frm) {
        update_crane_asset_controls(frm);
        if (["Shared Ownership", "Operated for Owner", "Operated by Partner"].includes(frm.doc.ownership_type)) {
            frm.set_value("enable_profit_sharing", 1);
            frm.set_value("operator_type", frm.doc.ownership_type === "Operated by Partner"
                ? "External Operator" : "Our Company");
        } else if (frm.doc.ownership_type === "Rented") {
            frm.set_value("enable_profit_sharing", 0);
        }
        return frm.trigger("set_partner_company_rules");
    },
    async set_partner_company_rules(frm) {
        const external_only = frm.doc.ownership_type === "Operated for Owner";
        frm.fields_dict.ownership_partners.grid.update_docfield_property("is_company", "read_only", external_only);
        if (external_only) {
            for (const row of frm.doc.ownership_partners || []) {
                if (row.is_company) await frappe.model.set_value(row.doctype, row.name, "is_company", 0);
            }
        }
    },
    enable_profit_sharing(frm) {
        if (frm.doc.enable_profit_sharing && !(frm.doc.ownership_partners || []).length) {
            const row = frm.add_child("ownership_partners", {
                is_company: frm.doc.ownership_type === "Operated for Owner" ? 0 : 1, ownership_percentage: 100,
                profit_percentage: 100,
            });
            frm._partner_ownership = frm._partner_ownership || {};
            frm._partner_ownership[row.name] = flt(row.ownership_percentage);
            frm.refresh_field("ownership_partners");
        }
    },
    onload(frm) {
        if (frm.is_new()) {
            for (const period of ["Hour", "Day", "Month"]) {
                if (!(frm.doc.period_prices || []).some(row => row.period === period))
                    frm.add_child("period_prices", { period, price: 0 });
            }
            frm.refresh_field("period_prices");
        }
        frm.fields_dict.period_prices.grid.cannot_add_rows = true;
        frm.fields_dict.period_prices.grid.cannot_delete_rows = true;
        frm.toggle_display("availability_tab", !frm.is_new());
    },
    refresh(frm) {
        update_crane_asset_controls(frm);
        frm.trigger("load_asset_values");
        render_crane_operations(frm);
        frm.trigger("set_partner_company_rules");
        frm._partner_ownership = Object.fromEntries((frm.doc.ownership_partners || []).map(
            row => [row.name, flt(row.ownership_percentage)]));
        frm.toggle_display("availability_tab", !frm.is_new());
        if (frm.is_new()) return;
        if (frm.doc.agreement_history && frappe.user.has_role(["Accounts Manager", "System Manager"])) {
            frm.add_custom_button(__("Change Agreement"), () => {
                frappe.prompt([{
                    fieldname: "effective_from", fieldtype: "Date", label: __("Effective From"),
                    reqd: 1, default: frappe.datetime.get_today(),
                }], values => {
                    frm.set_value({ agreement_effective_from: values.effective_from,
                        sharing_calculation: "Operating First" });
                    frm.scroll_to_field("operating_percentage");
                    frm.set_intro(__("Edit the operating percentage, operator and remaining balance shares, then save. Previous agreements and submitted settlements retain their original terms."));
                }, __("Change Agreement"), __("Edit Terms"));
            });
        }
        if (frm.doc.agreement_history && frappe.model.can_create("Crane Profit Settlement")) {
            frm.add_custom_button(__("Profit Settlement"), async () => {
                if (frm.is_dirty()) frappe.throw(__("Save your agreement before creating a settlement."));
                const { message } = await frappe.call({
                    method: "heavy_equipment_rental.profit_sharing.settlement_defaults",
                    args: { crane: frm.doc.name },
                });
                frappe.new_doc("Crane Profit Settlement", message);
            }, __("Create"));
            frm.add_custom_button(__("Profit Settlements"), () =>
                frappe.set_route("List", "Crane Profit Settlement", { crane: frm.doc.name }), __("View"));
        }
        if (frappe.model.can_create("Payment Entry")) {
            frm.add_custom_button(__("Payment"), async () => {
                await frappe.require("/assets/heavy_equipment_rental/js/rental_payments.js");
                return heavy_equipment_rental.create_supplier_payment(frm);
            }, __("Create"));
        }
        frm.add_custom_button(__("Resource Calendar"), () => {
            window.location.href = `/rental-calendar/timeline?crane=${encodeURIComponent(frm.doc.name)}`;
        }, __("View"));
        for (const [label, doctype] of [["Assignments", "Crane Assignment"],
            ["Timesheets", "Crane Timesheet"], ["Maintenance", "Crane Maintenance"],
            ["Expenses", "Expense Entry"]]) {
            if (doctype === "Crane Assignment") continue;
            frm.add_custom_button(__(label), () => frappe.set_route("List", doctype, { crane: frm.doc.name }), __("View"));
        }
        if (frappe.model.can_create("Expense Entry"))
            frm.add_custom_button(__("Expense"), () => frappe.new_doc("Expense Entry", { crane: frm.doc.name }), __("Create"));
        for (const [label, doctype] of [["Repair / Maintenance", "Crane Maintenance"], ["Timesheet", "Crane Timesheet"]]) {
            if (frappe.model.can_create(doctype))
                frm.add_custom_button(__(label), () => frappe.new_doc(doctype, { crane: frm.doc.name, ...(doctype === "Crane Maintenance" ? { company: frm.doc.sharing_company || frappe.defaults.get_user_default("Company"), cost_treatment: "Operating Expense" } : {}) }), __("Create"));
        }
        if (frappe.model.can_create("Sales Invoice")) {
            frm.add_custom_button(__("Sales Invoice"), () => frappe.call({
                method: "heavy_equipment_rental.billing.generate_crane_sales_invoices",
                args: { crane: frm.doc.name },
                freeze: true,
            }).then(({ message }) => {
                const invoices = message?.invoices || [];
                if (invoices.length === 1) {
                    frappe.set_route("Form", "Sales Invoice", invoices[0]);
                } else if (invoices.length > 1) {
                    const links = invoices.map(name =>
                        `<li><a href="/app/sales-invoice/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a></li>`
                    ).join("");
                    frappe.msgprint({ title: __("Draft Sales Invoices"),
                        message: `<ul>${links}</ul>`, indicator: "green" });
                } else {
                    frappe.msgprint(message?.submitted_assignments
                        ? __("All submitted work for this Crane is already billed.")
                        : __("No submitted Timesheets found for this Crane."));
                }
            }), __("Create"));
        }
        frm._calendar_month = frm._calendar_month || new Date(new Date().getFullYear(), new Date().getMonth(), 1);
        frm.trigger("load_availability");
    },
    asset(frm) {
        return frm.trigger("load_asset_values");
    },
    async load_asset_values(frm) {
        const wrapper = frm.fields_dict.asset_values.$wrapper;
        const request = frm._asset_request = (frm._asset_request || 0) + 1;
        wrapper.empty();
        if (!frm.doc.asset) return;
        if (frm.is_new() || frm.is_dirty()) {
            wrapper.text(__("Save the Crane to view the linked Asset and dated ownership values."));
            return;
        }
        if (!frappe.model.can_read("Asset")) {
            wrapper.text(__("Asset read permission is required to view financial values."));
            return;
        }
        wrapper.text(__("Loading Asset values..."));
        try {
            const { message: data } = await frappe.call({
                method: "heavy_equipment_rental.crane_assets.asset_summary",
                args: { crane: frm.doc.name },
            });
            if (request !== frm._asset_request) return;
            if (!data) { wrapper.empty(); return; }
            const esc = value => frappe.utils.escape_html(String(value ?? ""));
            const money = value => value === null ? __("Unavailable") : format_currency(value, data.currency);
            const warning = data.docstatus !== 1
                ? __("Draft or cancelled Asset: these values do not confirm posted asset balances.")
                : ["Sold", "Scrapped", "Capitalized"].includes(data.status)
                    ? __("This Asset has been disposed of. Review its native accounting records.") : "";
            wrapper.html(`<p><b>${esc(data.company)}</b> · ${esc(__(data.recognition_basis || "Company Interest Only"))} · ${esc(__(data.status))}
                · ${esc(__("Asset Owner"))}: ${esc(__(data.asset_owner))}
                · ${esc(__("Finance Book"))}: ${esc(data.finance_book || __("Default"))}</p>
                ${warning ? `<p class="text-warning">${esc(warning)}</p>` : ""}
                <p>${esc(__("Asset Gross Purchase Cost"))}: <b>${money(data.gross_purchase_amount)}</b>
                · ${esc(__("Capitalized Improvements"))}: <b>${money(data.additional_asset_cost)}</b>
                · ${esc(__("Current Value After Depreciation"))}: <b>${money(data.book_value)}</b></p>
                ${data.book_value === null ? `<p class="text-warning">${esc(__("The default Finance Book is missing from this Asset. Review its Finance Books."))}</p>` : ""}
                <p class="text-muted">${esc(__("Company ownership: {0}%. The Asset amounts already represent our interest; they are not multiplied by ownership again.", [data.company_ownership_percentage]))}</p>`);

        } catch (error) {
            if (request === frm._asset_request)
                wrapper.text(__("Asset values are unavailable. Check Asset read permission and accounting setup."));
        }
    },
    load_availability(frm) {
        if (frm.is_new()) return;
        const month = frm._calendar_month;
        const first = new Date(month.getFullYear(), month.getMonth(), 1);
        const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
        const date_string = day => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
        const request = frm._calendar_request = (frm._calendar_request || 0) + 1;
        const wrapper = frm.fields_dict.availability_overview.$wrapper;
        wrapper.html(`<p class="text-muted">${__("Loading reservations...")}</p>`);
        frappe.call({
            method: "heavy_equipment_rental.rental_queries.crane_availability",
            args: { crane: frm.doc.name, date: date_string(first), to_date: date_string(last) },
        }).then(({ message: data }) => {
            if (request !== frm._calendar_request || !data) return;
            const esc = value => frappe.utils.escape_html(String(value ?? ""));
            const bookings = [...data.bookings, ...data.future_reservations]
                .filter(row => row.expected_end_date >= date_string(first))
                .sort((a, b) => a.start_date.localeCompare(b.start_date));
            const weekdays = [__("Mon"), __("Tue"), __("Wed"), __("Thu"), __("Fri"), __("Sat"), __("Sun")]
                .map(day => `<div class="crane-calendar__weekday">${esc(day)}</div>`).join("");
            const offset = (first.getDay() + 6) % 7;
            const cells = [];
            const count = Math.ceil((offset + last.getDate()) / 7) * 7;
            for (let index = 0; index < count; index++) {
                const day = new Date(first.getFullYear(), first.getMonth(), index - offset + 1);
                const date = date_string(day);
                const outside = day.getMonth() !== first.getMonth();
                const booked = !outside && bookings.some(row => row.start_date <= date && row.expected_end_date >= date);
                const classes = ["crane-calendar__day", outside && "is-outside", booked && "is-booked",
                    date === frappe.datetime.get_today() && "is-today"].filter(Boolean).join(" ");
                cells.push(`<div class="${classes}" title="${booked ? esc(__("Reserved")) : ""}">${day.getDate()}${booked ? `<small>${__("Reserved")}</small>` : ""}</div>`);
            }
            const upcoming = bookings.filter(row => row.expected_end_date >= frappe.datetime.get_today()).slice(0, 5);
            const list = upcoming.length ? `<ul>${upcoming.map(row =>
                `<li><a href="/app/crane-assignment/${encodeURIComponent(row.assignment)}">${esc(row.assignment)}</a> · ${esc(row.start_date)} – ${esc(row.expected_end_date)} · ${esc(row.customer)}${row.location ? ` · ${esc(row.location)}` : ""}</li>`
            ).join("")}</ul>` : `<p class="text-muted">${__("No upcoming reservations")}</p>`;
            const title = first.toLocaleDateString(frappe.boot.lang || undefined, { month: "long", year: "numeric" });
            wrapper.html(`<div class="crane-calendar">
                <div class="crane-calendar__head"><h3>${esc(title)}</h3><div class="crane-calendar__nav">
                    <button type="button" data-month="-1" aria-label="${__("Previous month")}">‹</button>
                    <button type="button" data-month="0">${__("Today")}</button>
                    <button type="button" data-month="1" aria-label="${__("Next month")}">›</button>
                </div></div>
                <div class="crane-calendar__legend"><span>${__("Available")}</span><span class="is-booked">${__("Reserved")}</span></div>
                <div class="crane-calendar__grid">${weekdays}${cells.join("")}</div>
                <div class="crane-calendar__bookings"><h4>${__("Upcoming reservations")}</h4>${list}</div>
            </div>`);
            wrapper.find("[data-month]").on("click", event => {
                const change = Number(event.currentTarget.dataset.month);
                frm._calendar_month = change === 0
                    ? new Date(new Date().getFullYear(), new Date().getMonth(), 1)
                    : new Date(first.getFullYear(), first.getMonth() + change, 1);
                frm.trigger("load_availability");
            });
        }).catch(() => {
            if (request === frm._calendar_request)
                wrapper.html(`<p class="text-danger">${__("Could not load reservations")}</p>`);
        });
    },
});

frappe.ui.form.on("Crane Partner", {
    ownership_partners_add(frm, cdt, cdn) {
        frm._partner_ownership = frm._partner_ownership || {};
        frm._partner_ownership[cdn] = 0;
        return frm.trigger("is_company", cdt, cdn);
    },
    async ownership_percentage(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frm._partner_ownership = frm._partner_ownership || {};
        const previous = frm._partner_ownership[cdn] ?? 0;
        frm._partner_ownership[cdn] = flt(row.ownership_percentage);
        if (!row.allow_zero_profit_share && flt(row.profit_percentage) === previous) {
            await frappe.model.set_value(cdt, cdn, "profit_percentage", row.ownership_percentage);
        }
    },
    profit_percentage(frm, cdt, cdn) {
        if (flt(locals[cdt][cdn].profit_percentage) > 0) {
            return frappe.model.set_value(cdt, cdn, "allow_zero_profit_share", 0);
        }
    },
    is_company(frm, cdt, cdn) {
        if (frm.doc.ownership_type === "Operated for Owner" && locals[cdt][cdn].is_company) {
            frappe.msgprint(__("Operated for Owner allows external partners only. Our Company receives its operating share separately."));
            return frappe.model.set_value(cdt, cdn, "is_company", 0);
        }
    },
});
