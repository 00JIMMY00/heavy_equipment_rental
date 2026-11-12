frappe.ui.form.on("Expense Entry", {
    setup(frm) {
        frm.set_query("crane_assignment", () => ({ filters: { company: frm.doc.company } }));
    },
    crane_assignment: rental_expense_defaults,
    crane: rental_expense_defaults,
});

async function rental_expense_defaults(frm) {
    if (frm.doc.docstatus !== 0) return;
    const assignment = frm.doc.crane_assignment;
    const crane = frm.doc.crane;
    const request = frm._rental_expense_request = (frm._rental_expense_request || 0) + 1;
    await frm.set_value({ service_from_date: null, service_to_date: null });
    if (!assignment) return;
    const doc = await frappe.db.get_doc("Crane Assignment", assignment);
    if (request !== frm._rental_expense_request || assignment !== frm.doc.crane_assignment || crane !== frm.doc.crane) return;
    if (frm.doc.service_from_date || frm.doc.service_to_date) return;
    const booked = (doc.assigned_cranes || []).filter(r => !r.cancelled);
    const cranes = [...new Set(booked.map(r => r.crane))];
    if (!crane && cranes.length === 1) return frm.set_value("crane", cranes[0]);
    const rows = booked.filter(r => r.crane === crane);
    if (!rows.length) return;
    await frm.set_value({
        service_from_date: rows.map(r => r.start_date).sort()[0],
        service_to_date: rows.map(r => r.expected_end_date).sort().at(-1),
    });
}
