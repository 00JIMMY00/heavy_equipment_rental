frappe.ui.form.on("Crane", {
    onload(frm) {
        if (frm.is_new()) {
            for (const period of ["Hour", "Day", "Month", "Year"]) {
                if (!(frm.doc.period_prices || []).some(row => row.period === period))
                    frm.add_child("period_prices", { period, price: 0 });
            }
            frm.refresh_field("period_prices");
        }
        frm.fields_dict.period_prices.grid.cannot_add_rows = true;
        frm.fields_dict.period_prices.grid.cannot_delete_rows = true;
    },
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Resource Calendar"), () => {
            window.location.href = `/rental-calendar/timeline?crane=${encodeURIComponent(frm.doc.name)}`;
        }, __("View"));
        for (const [label, doctype] of [["Assignments", "Crane Assignment"],
            ["Timesheets", "Crane Timesheet"], ["Maintenance", "Crane Maintenance"],
            ["Expenses", "Expense Entry"]]) {
            if (doctype === "Crane Assignment") continue;
            frm.add_custom_button(__(label), () => frappe.set_route("List", doctype, { crane: frm.doc.name }), __("View"));
        }
        frm.trigger("availability_date");
    },
    availability_date(frm) {
        if (frm.is_new()) return;
        frappe.call({
            method: "heavy_equipment_rental.rental_queries.crane_availability",
            args: { crane: frm.doc.name, date: frm.doc.availability_date || frappe.datetime.get_today() },
        }).then(({ message: data }) => {
            if (!data) return;
            const esc = value => frappe.utils.escape_html(String(value ?? ""));
            const link = (doctype, name) => `<a href="/app/${doctype}/${encodeURIComponent(name)}">${esc(name)}</a>`;
            const bookings = [...data.bookings, ...data.future_reservations].map(row =>
                `<tr><td>${link("crane-assignment", row.assignment)}</td><td>${esc(row.customer)}</td><td>${esc(row.location)}</td><td>${esc(row.start_date)} – ${esc(row.expected_end_date)}</td><td>${row.rental_rate ? `${esc(row.rental_rate)} / ${esc(row.rental_rate_unit)}` : `<strong>${__("Set agreed rate")}</strong>`}</td></tr>`).join("");
            const sheets = data.timesheets.map(row => `<li>${link("crane-timesheet", row.name)} (${row.docstatus === 1 ? __("Submitted") : __("Draft")})</li>`).join("");
            const invoices = data.invoices.map(name => `<li>${link("sales-invoice", name)}</li>`).join("");
            const expenses = data.expenses.map(row => `<li>${link("expense-entry", row.name)} · ${esc(row.amount)}</li>`).join("");
            const maintenance = data.maintenance.map(row => `<li>${link("crane-maintenance", row.name)} · ${esc(row.status)} · ${esc(row.cost)}</li>`).join("");
            frm.fields_dict.availability_overview.$wrapper.html(`
                <p><b>${__("Availability")}:</b> ${data.available ? __("Available") : __("Unavailable")}
                · ${data.indicators.map(value => esc(__(value))).join(" · ")}</p>
                <h5>${__("Bookings")}</h5>${bookings ? `<table class="table table-bordered"><thead><tr><th>${__("Assignment")}</th><th>${__("Customer")}</th><th>${__("Location")}</th><th>${__("Dates")}</th><th>${__("Agreed rate")}</th></tr></thead><tbody>${bookings}</tbody></table>` : `<p>${__("None")}</p>`}
                <h5>${__("Timesheets")}</h5><ul>${sheets}</ul>
                <h5>${__("Maintenance")}</h5><ul>${maintenance}</ul>
                <h5>${__("Sales Invoices")}</h5><ul>${invoices}</ul>
                <h5>${__("Expenses")}</h5><ul>${expenses}</ul>`);
        });
    },
});
