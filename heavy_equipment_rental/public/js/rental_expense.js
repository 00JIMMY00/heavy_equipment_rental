frappe.ui.form.on("Expense Entry", {
    setup(frm) {
        frm.set_query("crane", () => frm.doc.crane_assignment ? {
            query: "heavy_equipment_rental.rental_expenses.assignment_cranes",
            filters: { assignment: frm.doc.crane_assignment },
        } : {});
        frm.set_query("crane_assignment", () => ({ filters: { company: frm.doc.company } }));
    },
    async crane_assignment(frm) {
        await rental_expense_defaults(frm);
        return expense_rental_context(frm, "assignment_changed");
    },
    async crane_timesheet(frm) {
        if (!frm.doc.crane_timesheet) await rental_expense_defaults(frm);
        return expense_rental_context(frm, "timesheet_changed");
    },
    crane(frm) { return expense_rental_context(frm, "autofill"); },
    company(frm) { return expense_rental_context(frm, "autofill"); },
    posting_date(frm) { return expense_rental_context(frm, "autofill"); },
    refresh(frm) { return expense_rental_context(frm, "setup"); },
});

async function rental_expense_defaults(frm) {
    if (frm.doc.docstatus !== 0 || frm._setting_rental_context) return;
    const assignment = frm.doc.crane_assignment;
    const crane = frm.doc.crane;
    const request = frm._rental_expense_request = (frm._rental_expense_request || 0) + 1;
    if (!assignment) return;
    const doc = await frappe.db.get_doc("Rental Contract", assignment);
    if (request !== frm._rental_expense_request || assignment !== frm.doc.crane_assignment || crane !== frm.doc.crane) return;
    const booked = (doc.assigned_cranes || []).filter(r => !r.cancelled);
    const cranes = [...new Set(booked.map(r => r.crane))];
    if (crane && !cranes.includes(crane)) return frm.set_value("crane", cranes.length === 1 ? cranes[0] : null);
    if (!crane && cranes.length === 1) return frm.set_value("crane", cranes[0]);

}

async function expense_rental_context(frm, method) {
    if (frm._setting_rental_context) return;
    await frappe.require("/assets/heavy_equipment_rental/js/rental_context.js");
    return heavy_equipment_rental.rental_context[method](frm);
}
