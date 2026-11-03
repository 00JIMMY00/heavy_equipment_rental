function fill_default_days(frm) {
    if (frm.doc.docstatus !== 0 || !frm.doc.period_start || !frm.doc.period_end) return;
    const start = frm.doc.period_start;
    const end = frm.doc.period_end;
    const request = (frm._default_days_request || 0) + 1;
    frm._default_days_request = request;
    frappe.call({
        method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet.default_timesheet_entries",
        args: { period_start: start, period_end: end },
    }).then(({ message: defaults }) => {
        if (request !== frm._default_days_request || frm.doc.period_start !== start || frm.doc.period_end !== end) return;
        const existing = new Set((frm.doc.timesheet_entries || []).map((row) => row.work_date));
        let added = false;
        for (const values of defaults || []) {
            if (existing.has(values.work_date)) continue;
            frm.add_child("timesheet_entries", { ...values, employee: frm.doc.driver || undefined });
            existing.add(values.work_date);
            added = true;
        }
        if (added) {
            frm.refresh_field("timesheet_entries");
            load_driver_names(frm);
            update_driver_hours(frm);
        }
    });
}

async function load_driver_names(frm) {
    const missing = [...new Set((frm.doc.timesheet_entries || [])
        .filter((row) => row.employee && !row.driver_name).map((row) => row.employee))];
    if (!missing.length) return;
    const names = await frappe.db.get_list("Employee", {
        filters: { name: ["in", missing] },
        fields: ["name", "employee_name"],
        limit: missing.length,
    });
    const by_id = Object.fromEntries(names.map((row) => [row.name, row.employee_name]));
    for (const row of frm.doc.timesheet_entries || []) {
        if (row.employee && !row.driver_name) row.driver_name = by_id[row.employee];
    }
    frm.refresh_field("timesheet_entries");
    update_driver_hours(frm);
}

function shift_hours(row) {
    if (!row.start_time || !row.end_time) return 0;
    const seconds = (value) => value.split(":").map(Number).reduce((total, part) => total * 60 + part, 0);
    let duration = seconds(row.end_time) - seconds(row.start_time);
    if (row.ends_next_day) duration += 24 * 3600;
    return duration > 0 ? duration / 3600 : 0;
}

function update_driver_hours(frm) {
    if (frm.doc.docstatus !== 0) return;
    const totals = new Map();
    for (const row of frm.doc.timesheet_entries || []) {
        if (!row.employee) continue;
        const current = totals.get(row.employee) || { employee: row.employee, driver_name: row.driver_name, total_hours: 0 };
        current.driver_name = row.driver_name || current.driver_name;
        current.total_hours += shift_hours(row);
        totals.set(row.employee, current);
    }
    frm.clear_table("driver_hours");
    for (const values of totals.values()) frm.add_child("driver_hours", values);
    frm.refresh_field("driver_hours");
}

async function load_timesheet_defaults(frm) {
    if (!frm.is_new() || frm.doc.docstatus !== 0 || frm._setting_rental_defaults) return;
    const crane = frm.doc.crane;
    const rate = frm.doc.rental_rate;
    const unit = frm.doc.rental_rate_unit;
    const request = (frm._rental_defaults_request || 0) + 1;
    frm._rental_defaults_request = request;
    const { message: defaults } = await frappe.call({
        method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet.get_timesheet_defaults",
        args: { crane, selling_uom: unit },
    });
    if (request !== frm._rental_defaults_request || frm.doc.crane !== crane ||
        frm.doc.rental_rate_unit !== unit || !frm.is_new() || frm.doc.docstatus !== 0) return;
    const values = {};
    if (!frm.doc.purchase_uom) values.purchase_uom = defaults.purchase_uom;
    if (!frm.doc.assignment) {
        if (!frm.doc.rental_rate_unit) values.rental_rate_unit = defaults.rental_rate_unit;
        if (defaults.rental_rate !== undefined && frm.doc.rental_rate === rate &&
            (!rate || rate === frm._default_selling_rate)) {
            values.rental_rate = defaults.rental_rate;
            frm._default_selling_rate = defaults.rental_rate;
        }
    }
    frm._setting_rental_defaults = true;
    try {
        await frm.set_value(values);
    } finally {
        frm._setting_rental_defaults = false;
    }
}

function purchase_price_label(frm) {
    frm.set_df_property("purchase_rate", "label", __("Purchase Price per {0}", [frm.doc.purchase_uom || "Hour"]));
}

async function load_rental_terms(frm) {
    if (frm.doc.docstatus !== 0 || !frm.doc.assignment) return;
    const { assignment, crane, period_start, period_end } = frm.doc;
    if (![crane, period_start, period_end].every(Boolean)) return;
    const rental = await frappe.db.get_doc("Crane Assignment", assignment);
    if ([assignment, crane, period_start, period_end].join("|") !==
        [frm.doc.assignment, frm.doc.crane, frm.doc.period_start, frm.doc.period_end].join("|")) return;
    const rows = rental.assigned_cranes.filter(row => row.crane === crane && !row.cancelled &&
        row.start_date <= period_start && row.expected_end_date >= period_end);
    await frm.set_value({
        rental_rate_unit: rows.length === 1 ? rows[0].rental_rate_unit : "",
        rental_rate: rows.length === 1 ? rows[0].rental_rate : 0,
    });
}

function suggest_assignment(frm) {
    if (frm.doc.assignment || !frm.is_new()) return;
    const { crane, customer, location, period_start, period_end } = frm.doc;
    if (![crane, customer, location, period_start, period_end].every(Boolean)) return;
    const key = [crane, customer, location, period_start, period_end].join("|");
    if (frm._assignment_prompt_key === key) return;
    frm._assignment_prompt_key = key;
    frappe.call({
        method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet.find_assignments",
        args: { crane, customer, location, period_start, period_end },
    }).then(({ message: matches }) => {
        if (frm.doc.assignment || frm._assignment_prompt_key !== key) return;
        if (matches?.length === 1) frm.set_value("assignment", matches[0]);
        if (matches?.length > 1) {
            const dialog = new frappe.ui.Dialog({
                title: __("Choose the rental Assignment"),
                fields: [{ fieldname: "assignment", fieldtype: "Select", label: __("Assignment"),
                    options: ["", ...matches].join("\n"), reqd: 1 }],
                primary_action_label: __("Use Assignment"),
                primary_action(values) {
                    frm.set_value("assignment", values.assignment);
                    dialog.hide();
                },
            });
            dialog.show();
        }
    });
}

frappe.ui.form.on("Crane Timesheet", {
    onload: load_timesheet_defaults,
    rental_rate_unit: load_timesheet_defaults,
    purchase_uom: purchase_price_label,
    setup(frm) {
        frm.set_query("assignment", () => ({ filters: Object.fromEntries([
            ["customer", frm.doc.customer], ["location", frm.doc.location],
        ].filter(([, value]) => value)) }));
    },
    async assignment(frm) {
        if (!frm.doc.assignment) return;
        const { message } = await frappe.db.get_value("Crane Assignment", frm.doc.assignment, ["customer", "location"]);
        if (message) {
            await frm.set_value({ customer: message.customer, location: message.location });
        }
        await load_rental_terms(frm);
    },
    async crane(frm) {
        if (frm.doc.docstatus === 0) {
            const name = frm.doc.crane;
            const crane = name ? (await frappe.db.get_value("Crane", name,
                ["ownership_type", "supplier"])).message : null;
            if (frm.doc.crane !== name) return;
            await frm.set_value({
                crane_ownership_type: crane?.ownership_type || "",
                rented: crane?.ownership_type === "Rented" ? 1 : 0,
                purchase_supplier: crane?.ownership_type === "Rented" ? crane.supplier : "",
            });
        }
        await load_timesheet_defaults(frm);
        await load_rental_terms(frm);
        suggest_assignment(frm);
    },
    customer: suggest_assignment,
    location: suggest_assignment,
    period_start(frm) { fill_default_days(frm); suggest_assignment(frm); load_rental_terms(frm); },
    period_end(frm) { fill_default_days(frm); suggest_assignment(frm); load_rental_terms(frm); },
    driver(frm) {
        if (!frm.doc.driver) return;
        let changed = false;
        for (const row of frm.doc.timesheet_entries || []) {
            if (row.employee) continue;
            row.employee = frm.doc.driver;
            changed = true;
        }
        if (changed) {
            frm.refresh_field("timesheet_entries");
            load_driver_names(frm);
            update_driver_hours(frm);
        }
    },
    refresh(frm) {
        purchase_price_label(frm);
        load_rental_terms(frm);
        if (frm.doc.docstatus === 1 && frm.doc.purchase_invoice && frappe.model.can_create("Payment Entry")) {
            frm.add_custom_button(__("Payment"), async () => {
                await frappe.require("/assets/heavy_equipment_rental/js/rental_payments.js");
                return heavy_equipment_rental.create_supplier_payment(frm);
            }, __("Create"));
        }
        if (frm.doc.docstatus === 0 && !(frm.doc.timesheet_entries || []).length) fill_default_days(frm);
        if (frm.doc.docstatus === 1 && frappe.model.can_create("Sales Invoice"))
            frm.add_custom_button(__("Generate Sales Invoice"), () => frappe.call({
                method: "heavy_equipment_rental.billing.generate_sales_invoice",
                args: { timesheet: frm.doc.name },
                freeze: true,
                callback: ({ message }) => {
                    if (message?.name) frappe.set_route("Form", "Sales Invoice", message.name);
                },
            }), __("Create"));
    },
});

frappe.ui.form.on("Timesheet Entry", {
    async employee(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.driver_name = null;
        if (row.employee) await load_driver_names(frm);
        update_driver_hours(frm);
    },
    driver_name: update_driver_hours,
    start_time: update_driver_hours,
    end_time: update_driver_hours,
    ends_next_day: update_driver_hours,
    timesheet_entries_add: update_driver_hours,
    timesheet_entries_remove: update_driver_hours,
});
