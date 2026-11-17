function crane_ownership_bar(doc, names = {}) {
    const esc = frappe.utils.escape_html;
    if (doc.hired_from_supplier) return `<div class="crane-ownership"><strong>${esc(__("Hired from Supplier"))}</strong><div>${esc(doc.supplier || "")}</div></div>`;
    const colors = ["#4169d1", "#138575", "#9a53c6", "#c47715", "#ce5268", "#387eaa", "#7b8738", "#875c48"];
    const rows = doc.ownership_partners || [];
    const owners = rows.map((row, index) => {
        const raw = Number(row.ownership_percentage);
        const percentage = Number.isFinite(raw) ? Math.max(0, raw) : 0;
        const name = row.is_company ? __("Our Company") : (names[row.shareholder] || row.shareholder || row.supplier || __("Partner"));
        return { percentage, name, color: colors[index % colors.length] };
    });
    const total = owners.reduce((sum, owner) => sum + owner.percentage, 0);
    const base = Math.max(100, total);
    const percent = value => `${Number(value.toFixed(2))}%`;
    const segments = owners.filter(owner => owner.percentage > 0).map(owner =>
        `<span class="crane-ownership__segment" style="width:${owner.percentage / base * 100}%;background:${owner.color}" title="${esc(owner.name)}: ${percent(owner.percentage)}"></span>`).join("");
    const legend = owners.map(owner => `<span class="crane-ownership__owner"><i style="background:${owner.color}" aria-hidden="true"></i><span>${esc(owner.name)}</span><b>${percent(owner.percentage)}</b></span>`).join("");
    const labels = {"Company Owned": __("Company Owned"), "Shared Ownership": __("Shared Ownership"), "Externally Owned": __("Externally Owned"), "Ownership Not Recorded": __("Ownership Not Recorded")};
    const classification = labels[doc.ownership_classification] || __("Ownership Not Recorded");
    const warning = rows.length && Math.abs(total - 100) > 0.000001
        ? `<div class="crane-ownership__warning">${esc(__("Ownership percentages must total 100%."))} ${esc(__("Total"))}: ${percent(total)}</div>` : "";
    return `<div class="crane-ownership"><div class="crane-ownership__heading">${esc(classification)}</div><div class="crane-ownership__bar" role="img" aria-label="${esc(owners.map(o => `${o.name}: ${percent(o.percentage)}`).join(", ") || classification)}">${segments}</div><div class="crane-ownership__legend">${legend}</div>${warning}</div>`;
}

function crane_company_share(doc) {
    if (doc.hired_from_supplier) return 0;
    const owners = doc.ownership_partners || [];
    return owners.filter(r => r.is_company).reduce((sum, row) => sum + flt(row.ownership_percentage), 0);
}

function update_crane_asset_controls(frm) {
    const share = crane_company_share(frm.doc);
    const basis = share ? (share === 100 ? "Company Owned" : "Company Interest Only") : "";
    frm.toggle_display("asset_section", share > 0 || Boolean(frm.doc.asset));
    frm.set_df_property("asset_accounting_basis", "options", "\nCompany Owned\nCompany Interest Only");
    if (frm.doc.asset_accounting_basis !== basis) {
        frm.doc.asset_accounting_basis = basis;
        frm.refresh_field("asset_accounting_basis");
    }
}

frappe.ui.form.on("Crane", {
    setup(frm) {
        frm.set_query("shareholder", "operating_fees", () => ({filters:{company:frm.doc.sharing_company}}));
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
    ownership_type(frm) { update_crane_asset_controls(frm); },
    async hired_from_supplier(frm) {
        if (frm.doc.hired_from_supplier) await frm.set_value("enable_profit_sharing", 0);
        return frm.trigger("ownership_summary");
    },
    ownership_summary(frm) {
        frm.toggle_display("ownership_partners", !frm.doc.hired_from_supplier);
        const rows = frm.doc.ownership_partners || [];
        const share = rows.filter(r => r.is_company).reduce((n,r) => n + flt(r.ownership_percentage), 0);
        const field = frm.fields_dict.ownership_classification;
        field.df.formatter = () => crane_ownership_bar(frm.doc, frm._ownership_names);
        field.$wrapper.addClass("crane-ownership-field");
        frm.set_df_property("ownership_classification", "description", "");
        frm.set_value("ownership_classification", frm.doc.hired_from_supplier ? "Hired from Supplier" : !rows.length ? "Ownership Not Recorded" : share === 100 ? "Company Owned" : share ? "Shared Ownership" : "Externally Owned");
        frm.refresh_field("ownership_classification");
        frm._ownership_names = frm._ownership_names || {};
        frm._ownership_name_requests = frm._ownership_name_requests || new Set();
        for (const row of rows) {
            if (row.is_company || !row.shareholder || frm._ownership_name_requests.has(row.shareholder)) continue;
            const shareholder = row.shareholder;
            frm._ownership_name_requests.add(shareholder);
            frappe.db.get_value("Shareholder", shareholder, "title").then(({message}) => {
                if (message?.title) {
                    frm._ownership_names[shareholder] = message.title;
                    frm.refresh_field("ownership_classification");
                }
            }).catch(() => {}); // Keep the permitted linked ID when the title is unavailable.
        }
        update_crane_asset_controls(frm);
    },
    set_partner_company_rules(frm) {
        frm.fields_dict.ownership_partners.grid.update_docfield_property("is_company", "read_only", 0);
    },
    async enable_profit_sharing(frm) {
        if (frm.doc.enable_profit_sharing) await frm.set_value("hired_from_supplier", 0);
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
    async onload(frm) {
        if (!frm.doc.default_selling_uom) {
            const unit = await frappe.db.get_single_value("Heavy Equipment Rental Settings", "default_selling_uom");
            if (!frm.doc.default_selling_uom) await frm.set_value("default_selling_uom", unit || "Hour");
        }
        if (frm.is_new()) {
            if (!(frm.doc.operating_fees || []).length) {
                frm.add_child("operating_fees", {is_company:1,basis:"Grand Total",percentage:0});
                frm.refresh_field("operating_fees");
            }
            if (!(frm.doc.ownership_partners || []).length && !frm.doc.hired_from_supplier) {
                frm.add_child("ownership_partners", {is_company:1, ownership_percentage:100, profit_percentage:100});
                frm.refresh_field("ownership_partners");
            }
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
        frm.trigger("ownership_summary");
        update_crane_asset_controls(frm);
        frm.trigger("load_asset_values");
        frm.trigger("set_partner_company_rules");
        frm._partner_ownership = Object.fromEntries((frm.doc.ownership_partners || []).map(
            row => [row.name, flt(row.ownership_percentage)]));
        frm.toggle_display("availability_tab", !frm.is_new());
        if (frm.is_new()) return;
        frm.add_custom_button(__("Resource Calendar"), () => {
            window.location.href = `/rental-calendar/timeline?crane=${encodeURIComponent(frm.doc.name)}`;
        }, __("View"));
        for (const [label, doctype] of [["Rental Contracts", "Rental Contract"],
            ["Timesheets", "Crane Timesheet"], ["Maintenance", "Crane Maintenance"],
            ["Expenses", "Expense Entry"]]) {
            if (doctype === "Rental Contract") continue;
            frm.add_custom_button(__(label), () => frappe.set_route("List", doctype, { crane: frm.doc.name }), __("View"));
        }
        for (const [label, doctype] of [["Equipment Work Log", "Crane Timesheet"],
            ["Equipment Expense", "Expense Entry"], ["Maintenance", "Crane Maintenance"]]) {
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
                        : __("No billable work has been recorded."));
                }
            }), __("Create"));
        }
        if (frm.doc.enable_profit_sharing && frappe.model.can_create("Crane Profit Settlement")) {
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
                `<li><a href="/app/rental-contract/${encodeURIComponent(row.assignment)}">${esc(row.assignment)}</a> · ${esc(row.start_date)} – ${esc(row.expected_end_date)} · ${esc(row.customer)}${row.location ? ` · ${esc(row.location)}` : ""}</li>`
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
        frm.trigger("ownership_summary");
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
    is_company(frm) { frm.trigger("ownership_summary"); },
    ownership_partners_remove(frm) { frm.trigger("ownership_summary"); },
    shareholder(frm) { frm.trigger("ownership_summary"); },
});

frappe.ui.form.on("Crane Operating Fee", {
    is_company(frm, cdt, cdn) {
        if (locals[cdt][cdn].is_company) frappe.model.set_value(cdt, cdn, "shareholder", null);
    }
});
