frappe.provide("heavy_equipment_rental");
heavy_equipment_rental.rental_context = {
    dates(frm) {
        const d = frm.doc;
        return d.doctype === "Expense Entry"
            ? [d.service_from_date || d.posting_date, d.service_to_date || d.service_from_date || d.posting_date]
            : [d.actual_start_date || frappe.datetime.get_today(), d.actual_end_date || d.actual_start_date || frappe.datetime.get_today()];
    },
    editable(frm) {
        return frm.doc.doctype === "Expense Entry" ? frm.doc.docstatus === 0 : !frm.doc.expense_entry && !["Completed", "Cancelled"].includes(frm.doc.status);
    },
    setup(frm) {
        const editable = this.editable(frm);
        for (const field of ["crane_assignment", "crane_timesheet"]) {
            frm.set_df_property(field, "read_only", !editable);
            frm.set_df_property(field, "reqd", 0);
            frm.set_query(field, () => {
                const [start, end] = this.dates(frm);
                const late_assignment = frm.doc.doctype === "Expense Entry" && field === "crane_assignment";
                return {query:"heavy_equipment_rental.rental_context.context_link_query", filters:{
                    crane:frm.doc.crane, company:frm.doc.company,
                    from_date:late_assignment ? null : start, to_date:late_assignment ? null : end,
                    assignment:field === "crane_timesheet" ? frm.doc.crane_assignment : null,
                }};
            });
        }
        const first_load = !frm._rental_context_initialized;
        frm._rental_context_initialized = true;
        if (first_load && frm.is_new?.() && !frm.doc.crane_assignment && !frm.doc.crane_timesheet) {
            return this.autofill(frm);
        }
        return this.changed(frm, false);
    },
    async changed(frm, clear_invalid = true) {
        if (frm._setting_rental_context || !this.editable(frm)) return;
        const crane = frm.doc.crane, assignment = frm.doc.crane_assignment;
        const [start,end] = this.dates(frm);
        const request = frm._work_request = (frm._work_request || 0) + 1;
        if (!crane || !start || !end || start > end) {
            frm.set_df_property("crane_assignment","reqd",0);
            frm.set_df_property("crane_timesheet","reqd",0);
            return;
        }
        const {message: options} = await frappe.call({method:"heavy_equipment_rental.rental_context.rental_work_options",
            args:{crane,start,end,company:frm.doc.company}});
        if (request !== frm._work_request || crane !== frm.doc.crane || assignment !== frm.doc.crane_assignment ||
            this.dates(frm).join('|') !== [start,end].join('|')) return;
        const sheets = options.timesheets.filter(r=>!assignment || r.assignment === assignment);
        frm.set_df_property("crane_assignment","reqd",0);
        frm.set_df_property("crane_timesheet","reqd",0);
        if (!clear_invalid) return;
        const values = {};
        if (assignment && !options.assignments.some(r=>r.name === assignment)) {
            values.crane_assignment = null;
            values.crane_timesheet = null;
            if (frm.doc.doctype === "Expense Entry") Object.assign(values,{service_from_date:null,service_to_date:null});
        } else if (frm.doc.crane_timesheet && !sheets.some(r=>r.name === frm.doc.crane_timesheet)) values.crane_timesheet = null;
        if (Object.keys(values).length) {
            frm._setting_rental_context = true;
            try { await frm.set_value(values); } finally { frm._setting_rental_context = false; }
            return this.changed(frm,false);
        }
    },
    async autofill(frm) {
        if (frm._setting_rental_context || !this.editable(frm)) return;
        const crane = frm.doc.crane;
        const start = frm.doc.doctype === "Expense Entry" ? frm.doc.posting_date : frm.doc.actual_start_date;
        const fields = ["crane", "company", "posting_date", "actual_start_date", "crane_assignment", "crane_timesheet"];
        const snapshot = fields.map(f=>frm.doc[f]).join("|");
        const request = frm._work_request = (frm._work_request || 0) + 1;
        if (!crane || !start) return;
        const {message: options} = await frappe.call({method:"heavy_equipment_rental.rental_context.rental_work_options",
            args:{crane,start,end:start,company:frm.doc.company}});
        if (request !== frm._work_request || fields.map(f=>frm.doc[f]).join("|") !== snapshot) return;
        const assignment = options.assignments.length === 1 ? options.assignments[0] :
            options.assignments.find(r=>r.name === frm.doc.crane_assignment);
        const sheets = options.timesheets.filter(r=>!assignment || r.assignment === assignment.name);
        const sheet = sheets.length === 1 ? sheets[0] : sheets.find(r=>r.name === frm.doc.crane_timesheet);
        const values = {crane_assignment:sheet?.assignment || assignment?.name || null, crane_timesheet:sheet?.name || null};
        if (frm.doc.doctype === "Expense Entry") Object.assign(values,{
            service_from_date:sheet?.start || assignment?.start || null,
            service_to_date:sheet?.end || assignment?.end || null,
        });
        frm._setting_rental_context = true;
        try { await frm.set_value(values); } finally { frm._setting_rental_context = false; }
    },
    async assignment_changed(frm) {
        if (frm._setting_rental_context || !this.editable(frm)) return;
        frm._setting_rental_context = true;
        try { await frm.set_value("crane_timesheet",null); }
        finally { frm._setting_rental_context = false; }
        return this.changed(frm);
    },
    async timesheet_changed(frm) {
        if (frm._setting_rental_context || !this.editable(frm)) return;
        const name = frm.doc.crane_timesheet;
        if (!name) return this.changed(frm);
        const sheet = await frappe.db.get_doc("Crane Timesheet",name);
        if (frm.doc.crane_timesheet !== name || sheet.crane !== frm.doc.crane) return;
        const values = {crane_assignment:sheet.assignment};
        if (frm.doc.doctype === "Expense Entry") Object.assign(values,
            {service_from_date:sheet.period_start,service_to_date:sheet.period_end});
        frm._setting_rental_context = true;
        try { await frm.set_value(values); }
        finally { frm._setting_rental_context = false; }
        return this.changed(frm);
    },
};
