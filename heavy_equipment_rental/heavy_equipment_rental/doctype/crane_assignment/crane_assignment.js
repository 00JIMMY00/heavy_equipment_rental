frappe.ui.form.on("Crane Assignment", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (frappe.model.can_create("Expense Entry"))
            frm.add_custom_button(__("Expense"), () =>
                frappe.new_doc("Expense Entry", { crane_assignment: frm.doc.name }), __("Create"));
        frm.add_custom_button(__("New Timesheet"), () => {
            if (frm.is_dirty()) return frappe.msgprint(__("Save the Assignment before creating a Timesheet."));
            const cranes = [...new Set((frm.doc.assigned_cranes || []).filter(r => !r.cancelled && r.crane).map(r => r.crane))];
            const create = crane => {
                const bookings = frm.doc.assigned_cranes.filter(r => !r.cancelled && r.crane === crane);
                const open = booking => frappe.new_doc("Crane Timesheet", {
                    assignment: frm.doc.name, customer: frm.doc.customer,
                    location: frm.doc.location, crane,
                    period_start: booking.start_date,
                    period_end: booking.expected_end_date,
                });
                if (bookings.length === 1) return open(bookings[0]);
                frappe.prompt([{
                    fieldname: "booking", fieldtype: "Select", label: __("Rental Period"), reqd: 1,
                    options: bookings.map((r, index) => ({ value: String(index),
                        label: `${r.start_date} → ${r.expected_end_date}` })),
                }], values => open(bookings[Number(values.booking)]), __("Choose Rental Period"), __("Create Timesheet"));
            };
            if (!cranes.length) return frappe.msgprint(__("Add an active Crane to the Assignment first."));
            if (cranes.length === 1) return create(cranes[0]);
            frappe.prompt([{
                fieldname: "crane", fieldtype: "Link", label: __("Crane"), options: "Crane", reqd: 1,
                get_query: () => ({ filters: { name: ["in", cranes] } }),
            }], values => {
                if (!cranes.includes(values.crane)) return frappe.msgprint(__("Select a Crane from this Assignment."));
                return create(values.crane);
            }, __("Choose Crane for Timesheet"), __("Create Timesheet"));
        }, __("Create"));
        frm.add_custom_button(__("Timesheets"), () =>
            frappe.set_route("List", "Crane Timesheet", { assignment: frm.doc.name }), __("View"));
        if (frappe.model.can_create("Sales Invoice")) {
            frm.add_custom_button(__("Generate Sales Invoice"), () => frappe.call({
                method: "heavy_equipment_rental.billing.generate_sales_invoice",
                args: { assignment: frm.doc.name },
                freeze: true,
                callback: ({ message }) => {
                    if (message?.name) frappe.set_route("Form", "Sales Invoice", message.name);
                    else if (message?.already_exists) frappe.msgprint(__("All submitted work is already billed."));
                },
            }), __("Create"));
        }
        frm.add_custom_button(__("Resource Timeline"), () => {
            window.location.href = `/rental-calendar/timeline?assignment=${encodeURIComponent(frm.doc.name)}`;
        }, __("View"));
    },
});


frappe.ui.form.on("Assigned Crane", {
    assigned_cranes_add: assignment_row_defaults,
    crane: assignment_row_defaults,
    rental_rate_unit: assignment_row_defaults,
});

async function assignment_row_defaults(frm, cdt, cdn) {
    const row = locals[cdt]?.[cdn];
    if (!row || row._setting_rental_defaults) return;
    const crane = row.crane, unit = row.rental_rate_unit, rate = row.rental_rate;
    const request = row._rental_defaults_request = (row._rental_defaults_request || 0) + 1;
    const { message } = await frappe.call({
        method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_assignment.crane_assignment.get_assignment_defaults",
        args: { crane, rental_rate_unit: unit },
    });
    if (locals[cdt]?.[cdn] !== row || request !== row._rental_defaults_request || row.crane !== crane || row.rental_rate_unit !== unit) return;
    const values = {};
    if (!unit) values.rental_rate_unit = message.rental_rate_unit;
    if (message.rental_rate !== undefined && row.rental_rate === rate &&
            (!rate || rate === row._default_rental_rate)) {
        values.rental_rate = message.rental_rate;
        row._default_rental_rate = message.rental_rate;
    }
    row._setting_rental_defaults = true;
    try { await frappe.model.set_value(cdt, cdn, values); }
    finally { row._setting_rental_defaults = false; }
}
