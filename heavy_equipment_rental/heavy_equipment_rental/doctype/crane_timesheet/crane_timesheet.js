async function fill_default_days(frm, manual = false) {
    const doc = frm.doc;
    if (doc.docstatus !== 0) return;
    const { period_start: start, period_end: end } = doc;
    if (!start || !end) {
        if (manual) frappe.msgprint(__("Enter Period Start and Period End in Timesheet Details first."));
        return;
    }
    const request = (frm._default_days_request || 0) + 1;
    frm._default_days_request = request;
    const is_current = () => request === frm._default_days_request && frm.doc === doc &&
        doc.docstatus === 0 && doc.period_start === start && doc.period_end === end;
    const { message: defaults } = await frappe.call({
        method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet.default_timesheet_entries",
        args: { period_start: start, period_end: end },
    });
    if (!defaults?.length || !is_current()) return;

    const outside_period = (row) => row.work_date && (row.work_date < start || row.work_date > end);
    const outside = manual ? (doc.timesheet_entries || []).filter(outside_period) : [];
    if (outside.length) {
        const confirmed = await new Promise(resolve => {
            frappe.confirm(
                __("Remove {0} operator shift row(s) with work dates outside {1} through {2}? The rows will be deleted when you save the Timesheet.", [
                    outside.length, frappe.datetime.str_to_user(start), frappe.datetime.str_to_user(end),
                ]),
                () => resolve(true),
                () => resolve(false),
                __("Remove and Fill"),
                __("Cancel"),
            );
        });
        if (!confirmed || !is_current()) return;

        for (const row of outside.filter(outside_period)) {
            frappe.model.clear_doc(row.doctype, row.name);
        }
        frm.dirty();
    }

    const existing = new Set((doc.timesheet_entries || []).map((row) => row.work_date));
    const missing = defaults.filter((row) => !existing.has(row.work_date));
    if (!missing.length && !outside.length) {
        if (manual) frappe.show_alert(__("Timesheet Entries already has a row for every date in this period."));
        return;
    }
    for (const values of missing) {
        frm.add_child("timesheet_entries", {
            ...values,
            employee: doc.driver || undefined,
            rental_rate_unit: doc.rental_rate_unit,
            rental_rate: doc.rental_rate,
        });
    }
    frm.refresh_field("timesheet_entries");
    sync_payroll_drivers(frm);
    await load_driver_names(frm);
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
}

function payroll_work_by_driver(shifts) {
    const drivers = new Map();
    for (const row of shifts) {
        if (!row.employee) continue;
        const hours = flt((drivers.get(row.employee)?.quantity || 0) +
            flt(row.worked_hours) + flt(row.overtime_hours), 6);
        const overtime = flt((drivers.get(row.employee)?.overtime_hours || 0) + flt(row.overtime_hours), 6);
        drivers.set(row.employee, {unit: "Hour", quantity: hours, worked_hours: hours, overtime_hours: overtime});
    }
    return drivers;
}

function sync_payroll_drivers(frm) {
    const shifts = frm.doc.timesheet_entries || [];
    const payroll = frm.doc.driver_payroll || [];
    const grid = frm.fields_dict.driver_payroll.grid;
    const unit = frm.doc.docstatus ? payroll[0]?.unit : "Hour";
    const labels = {
        Hour: [__("Hours"), __("Price / Hour")],
        Day: [__("Days"), __("Price / Day")],
        Month: [__("Months"), __("Price / Month")],
    };
    const [quantityLabel, rateLabel] = labels[unit] || labels.Hour;
    for (const [field, label] of [["quantity", quantityLabel], ["rate", rateLabel]]) {
        const df = grid.docfields?.find(df => df.fieldname === field);
        if (df && df.label !== label) grid.update_docfield_property(field, "label", label);
    }
    if (frm.doc.docstatus !== 0) return;
    const drivers = payroll_work_by_driver(shifts);
    const amountField = frappe.meta.get_docfield("Crane Driver Payroll", "amount", frm.docname);
    const rateField = frappe.meta.get_docfield("Crane Driver Payroll", "rate", frm.docname);
    let rowsChanged = false;
    for (const row of [...payroll]) {
        const work = drivers.get(row.employee);
        if (work) {
            drivers.delete(row.employee);
            const rate = flt(row.rate);
            const amount = flt(row.amount);
            const overtimePrice = flt(row.overtime_price);
            if (["Day", "Month"].includes(row.unit) || cint(row.fixed_amount) || (amount > 0 && !rate && !overtimePrice)) {
                work.fixed_amount = 1;
                work.overtime_price = 0;
                const precision = frappe.meta.get_field_precision(rateField, row);
                work.rate = work.quantity > 0 && amount ? flt(amount / work.quantity, precision) : null;
            } else if (rate || overtimePrice || amount) {
                const precision = frappe.meta.get_field_precision(amountField, row);
                work.amount = flt(rate * (work.worked_hours - work.overtime_hours) +
                    (overtimePrice || rate) * work.overtime_hours, precision);
            }
            for (const [field, value] of Object.entries(work)) {
                if (row[field] === value) continue;
                row[field] = value;
                frm.dirty();
                grid.set_value(field, value, row);
            }
            continue;
        }
        if (flt(row.amount) || flt(row.overtime_price) || (flt(row.rate) && !cint(row.fixed_amount))) continue;
        frappe.model.clear_doc(row.doctype, row.name);
        rowsChanged = true;
    }
    for (const [employee, work] of drivers) {
        frm.add_child("driver_payroll", {employee, ...work});
        rowsChanged = true;
    }
    refresh_salary_balance(frm);
    if (rowsChanged) {
        frm.dirty();
        frm.refresh_field("driver_payroll");
    }
}

async function refresh_salary_balance(frm, force = false) {
    const wrapper = frm.fields_dict.salary_balance.$wrapper;
    const doc = frm.doc;
    const employees = [...new Set((doc.driver_payroll || []).map(row => row.employee).filter(Boolean))];
    const key = JSON.stringify([doc.name, doc.payroll_company, employees]);
    if (!force && frm.salary_balance_request?.key === key) return;
    const request = {key};
    frm.salary_balance_request = request;
    wrapper.empty();
    if (!employees.length || !frappe.boot.user.all_reports?.["Employee Salary Withdrawals"]) return;
    const balances = await frappe.xcall("heavy_equipment_rental.employee_salary.driver_salary_balances",
        {employees, company: doc.payroll_company || null});
    if (frm.doc !== doc || frm.salary_balance_request !== request || !balances.length) return;
    const table = $('<table class="table table-bordered">').appendTo(wrapper);
    const header = $('<tr>').appendTo($('<thead>').appendTo(table));
    for (const label of ["Driver", "Salary Difference"]) {
        $('<th scope="col">').text(__(label)).appendTo(header);
    }
    const body = $('<tbody>').appendTo(table);
    for (const balance of balances) {
        const row = $('<tr>').appendTo(body);
        $('<td>').text(balance.driver).appendTo(row);
        const value = balance.difference;
        const color = value < 0 ? "text-danger" : value > 0 ? "text-success" : "text-muted";
        $('<td>').addClass(color).text(format_currency(value, balance.currency)).appendTo(row);
    }
}

async function pay_timesheet_salary(frm) {
    const drivers = frm.doc.driver_payroll || [];
    if (!drivers.length) return frappe.msgprint(__("Add a driver to the Timesheet first."));
    const selected = frm.fields_dict.driver_payroll.grid.get_selected_children();
    if (drivers.length === 1 || selected.length === 1) {
        return open_salary_payment(frm, (selected[0] || drivers[0]).employee);
    }
    frappe.prompt({
        fieldname: "employee", fieldtype: "Select", label: __("Driver"), reqd: 1,
        options: drivers.map(row => ({
            value: row.employee,
            label: (frm.doc.timesheet_entries || []).find(shift => shift.employee === row.employee)?.driver_name || row.employee,
        })),
    }, values => open_salary_payment(frm, values.employee), __("Pay Salary / Advance"), __("Create"));
}

async function open_salary_payment(frm, employee) {
    if (frm.is_dirty() || frm.is_new()) await frm.save();
    if (frm.is_dirty() || frm.is_new()) return;
    const payment = await frappe.xcall("heavy_equipment_rental.driver_payroll.make_salary_payment",
        {timesheet: frm.doc.name, employee});
    await frappe.model.with_doctype("Grouped Expense");
    const [doc] = frappe.model.sync(payment);
    await frappe.set_route("Form", doc.doctype, doc.name);
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
        args: { crane, selling_uom: frm.doc.assignment || unit === frm._default_selling_unit ? null : unit },
    });
    if (request !== frm._rental_defaults_request || frm.doc.crane !== crane ||
        frm.doc.rental_rate_unit !== unit || !frm.is_new() || frm.doc.docstatus !== 0) return;
    const values = {};
    if (!frm.doc.purchase_uom) values.purchase_uom = defaults.purchase_uom;
    if (!frm.doc.assignment) {
        if (!unit || unit === frm._default_selling_unit) {
            values.rental_rate_unit = defaults.rental_rate_unit;
            frm._default_selling_unit = defaults.rental_rate_unit;
        }
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

async function load_rental_terms(frm, reset = false) {
    if (frm.doc.docstatus !== 0 || !frm.doc.assignment) return;
    const { assignment, crane, period_start, period_end } = frm.doc;
    if (![crane, period_start, period_end].every(Boolean)) return;
    const rental = await frappe.db.get_doc("Rental Contract", assignment);
    if ([assignment, crane, period_start, period_end].join("|") !==
        [frm.doc.assignment, frm.doc.crane, frm.doc.period_start, frm.doc.period_end].join("|")) return;
    const rows = rental.assigned_cranes.filter(row => row.crane === crane && !row.cancelled &&
        row.start_date <= period_start && row.expected_end_date >= period_end);
    const key = [assignment, crane, rows.map(r => r.name).join(",")].join("|");
    if (frm._loaded_rental_terms === key) return;
    const inherited = frm._inherited_rental_terms;
    if (!reset && frm.doc.rental_rate_unit && (!inherited ||
        frm.doc.rental_rate_unit !== inherited.unit || frm.doc.rental_rate !== inherited.rate)) return;
    frm._loaded_rental_terms = key;
    frm._inherited_rental_terms = {unit: rows.length === 1 ? rows[0].rental_rate_unit : "",
        rate: rows.length === 1 ? rows[0].rental_rate : 0};
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
                title: __("Choose the rental Rental Contract"),
                fields: [{ fieldname: "assignment", fieldtype: "Select", label: __("Rental Contract"),
                    options: ["", ...matches].join("\n"), reqd: 1 }],
                primary_action_label: __("Use Rental Contract"),
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
    async rental_rate_unit(frm) {
        sync_payroll_drivers(frm);
        await load_timesheet_defaults(frm);
        await fill_entry_rental_terms(frm);
    },
    rental_rate: fill_entry_rental_terms,
    purchase_uom: purchase_price_label,
    setup(frm) {
        const payroll = frm.fields_dict.driver_payroll.grid;
        payroll.df.cannot_add_rows = true;
        payroll.df.cannot_delete_rows = true;
        frm.set_query("mode_of_payment", "driver_payroll", () => ({filters: {enabled: 1}}));
        frm.set_query("assignment", () => ({ filters: Object.fromEntries([
            ["customer", frm.doc.customer], ["location", frm.doc.location],
        ].filter(([, value]) => value)) }));
    },
    async assignment(frm) {
        if (!frm.doc.assignment) return;
        const { message } = await frappe.db.get_value("Rental Contract", frm.doc.assignment, ["customer", "location"]);
        if (message) {
            await frm.set_value({ customer: message.customer, location: message.location });
        }
        await load_rental_terms(frm, true);
        await fill_entry_rental_terms(frm);
    },
    async crane(frm) {
        if (frm.doc.docstatus === 0) {
            const name = frm.doc.crane;
            const crane = name ? (await frappe.db.get_value("Crane", name,
                ["ownership_type", "hired_from_supplier", "supplier"])).message : null;
            if (frm.doc.crane !== name) return;
            await frm.set_value({
                crane_ownership_type: crane?.hired_from_supplier ? "Rented" : (crane?.ownership_type || ""),
                rented: crane?.hired_from_supplier ? 1 : 0,
                purchase_supplier: crane?.hired_from_supplier ? crane.supplier : "",
            });
        }
        await load_timesheet_defaults(frm);
        await load_rental_terms(frm, true);
        await fill_entry_rental_terms(frm);
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
            sync_payroll_drivers(frm);
        }
    },
    refresh(frm) {
        for (const field of ["rental_rate_unit", "purchase_uom"]) {
            const options = frm.doc[field] === "Month" ? "\nHour\nDay\nMonth" : "\nHour\nDay";
            frm.set_df_property(field, "options", options);
        }
        if (frm.doc.docstatus !== 2 && frappe.model.can_create("Grouped Expense")) {
            frm.add_custom_button(__("Pay Salary / Advance"), () => pay_timesheet_salary(frm), __("Create"));
        }
        refresh_salary_balance(frm, true);
        sync_payroll_drivers(frm);
        fill_entry_rental_terms(frm);
        purchase_price_label(frm);
        if (!frm.doc.rental_rate_unit) load_rental_terms(frm);
        if (frm.doc.profit_settlement) frm.add_custom_button(__("Profit Settlement"), () =>
            frappe.set_route("Form", "Crane Profit Settlement", frm.doc.profit_settlement), __("View"));
        if (frm.doc.docstatus === 1 && frm.doc.purchase_invoice && frappe.model.can_create("Payment Entry")) {
            frm.add_custom_button(__("Payment"), async () => {
                await frappe.require("/assets/heavy_equipment_rental/js/rental_payments.js");
                return heavy_equipment_rental.create_supplier_payment(frm);
            }, __("Create"));
        }
        const shifts = frm.fields_dict.timesheet_entries.grid;
        const fill_label = __("Fill Table");
        if (frm.doc.docstatus === 0 && shifts.is_editable()) {
            shifts.add_custom_button(fill_label, () => fill_default_days(frm, true), "top");
            if (!(frm.doc.timesheet_entries || []).length) fill_default_days(frm);
        } else {
            shifts.custom_buttons?.[fill_label]?.addClass("hidden");
        }
        if (frm.doc.docstatus === 1 && (frm.doc.total_crane_billable_hours > 0 || frm.doc.sales_invoice) &&
            frappe.model.can_create("Sales Invoice"))
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

function payroll_price_changed(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    row.fixed_amount = 0;
    if (!flt(row.rate) && !flt(row.overtime_price)) {
        row.amount = null;
        frm.fields_dict.driver_payroll.grid.set_value("amount", null, row);
    }
    sync_payroll_drivers(frm);
}

frappe.ui.form.on("Crane Driver Payroll", {
    async form_render(frm, cdt, cdn) {
        const doc = frm.doc;
        const row = locals[cdt][cdn];
        const assignment = doc.assignment;
        if (doc.docstatus !== 0 || row.mode_of_payment || !assignment) return;
        const mode = await frappe.xcall(
            "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.crane_timesheet.get_default_payroll_mode",
            {assignment},
        );
        if (mode && frm.doc === doc && doc.docstatus === 0 && doc.assignment === assignment &&
            locals[cdt][cdn] === row && !row.mode_of_payment) {
            await frappe.model.set_value(cdt, cdn, "mode_of_payment", mode);
        }
    },
    rate: payroll_price_changed,
    overtime_price: payroll_price_changed,
    amount(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.fixed_amount = 1;
        sync_payroll_drivers(frm);
    },
});

frappe.ui.form.on("Timesheet Entry", {
    async employee(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        row.driver_name = null;
        sync_payroll_drivers(frm);
        if (row.employee) await load_driver_names(frm);
    },
    worked_hours: sync_payroll_drivers,
    overtime_hours: sync_payroll_drivers,
    end_time: sync_payroll_drivers,
    ends_next_day: sync_payroll_drivers,
    timesheet_entries_add(frm) { sync_payroll_drivers(frm); fill_entry_rental_terms(frm); },
    async work_date(frm, cdt, cdn) {
        const date = moment(locals[cdt][cdn].work_date, "YYYY-MM-DD", true);
        await frappe.model.set_value(cdt, cdn, "day_name", date.isValid() ? date.locale("en").format("ddd") : "");
        sync_payroll_drivers(frm);
        await fill_entry_rental_terms(frm);
    },
    timesheet_entries_remove: sync_payroll_drivers,
});


async function fill_entry_rental_terms(frm) {
    if (frm.doc.docstatus !== 0 || !frm.doc.assignment || !frm.doc.crane) return;
    const assignment = frm.doc.assignment, crane = frm.doc.crane;
    const request = frm._entry_terms_request = (frm._entry_terms_request || 0) + 1;
    const doc = await frappe.db.get_doc("Rental Contract", assignment);
    if (request !== frm._entry_terms_request || frm.doc.assignment !== assignment || frm.doc.crane !== crane || frm.doc.docstatus !== 0) return;
    for (const row of frm.doc.timesheet_entries || []) {
        const day = row.work_date || frm.doc.period_start;
        const bookings = (doc.assigned_cranes || []).filter(r => !r.cancelled && r.crane === crane &&
            day && r.start_date <= day && day <= r.expected_end_date);
        await frappe.model.set_value(row.doctype, row.name, {
            rental_rate: frm.doc.rental_rate_unit ? frm.doc.rental_rate : (bookings.length === 1 ? bookings[0].rental_rate : null),
            rental_rate_unit: frm.doc.rental_rate_unit || (bookings.length === 1 ? bookings[0].rental_rate_unit : ""),
        });
    }
    sync_payroll_drivers(frm);
}
