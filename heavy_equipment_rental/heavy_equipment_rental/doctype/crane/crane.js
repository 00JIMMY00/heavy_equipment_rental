frappe.ui.form.on("Crane", {
    setup(frm) {
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
    ownership_type(frm) {
        if (["Shared Ownership", "Operated for Owner", "Operated by Partner"].includes(frm.doc.ownership_type)) {
            frm.set_value("enable_profit_sharing", 1);
            frm.set_value("operator_type", frm.doc.ownership_type === "Operated by Partner"
                ? "External Operator" : "Our Company");
        } else if (frm.doc.ownership_type === "Rented") {
            frm.set_value("enable_profit_sharing", 0);
        }
        frm.trigger("sync_company_ownership_type");
    },
    sync_company_ownership_type(frm) {
        if (frm.doc.ownership_type !== "Operated for Owner" || frm.doc.operator_type !== "Our Company"
            || !(frm.doc.ownership_partners || []).some(row => row.is_company && flt(row.ownership_percentage) > 0)) return;
        return frm.set_value("ownership_type", "Shared Ownership").then(() => {
            frappe.show_alert({ message: __("Ownership Type changed to Shared Ownership because Our Company owns a share. Operating and remaining balance percentages are kept."),
                indicator: "blue" });
        });
    },
    enable_profit_sharing(frm) {
        if (frm.doc.enable_profit_sharing && !(frm.doc.ownership_partners || []).length) {
            frm.add_child("ownership_partners", {
                is_company: 1, ownership_percentage: frm.doc.ownership_type === "Operated for Owner" ? 0 : 100,
                profit_percentage: 100,
            });
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
        for (const [label, doctype] of [["Maintenance", "Crane Maintenance"], ["Timesheet", "Crane Timesheet"]]) {
            if (frappe.model.can_create(doctype))
                frm.add_custom_button(__(label), () => frappe.new_doc(doctype, { crane: frm.doc.name }), __("Create"));
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
    ownership_percentage(frm) {
        return frm.trigger("sync_company_ownership_type");
    },
    is_company(frm) {
        return frm.trigger("sync_company_ownership_type");
    },
});
