frappe.ui.form.on("Crane", {
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
        frm.add_custom_button(__("Resource Calendar"), () => {
            window.location.href = `/rental-calendar/timeline?crane=${encodeURIComponent(frm.doc.name)}`;
        }, __("View"));
        for (const [label, doctype] of [["Assignments", "Crane Assignment"],
            ["Timesheets", "Crane Timesheet"], ["Maintenance", "Crane Maintenance"],
            ["Expenses", "Expense Entry"]]) {
            if (doctype === "Crane Assignment") continue;
            frm.add_custom_button(__(label), () => frappe.set_route("List", doctype, { crane: frm.doc.name }), __("View"));
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
