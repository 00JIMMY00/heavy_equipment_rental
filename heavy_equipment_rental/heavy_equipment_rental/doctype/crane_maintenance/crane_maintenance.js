frappe.ui.form.on("Crane Maintenance", {
	setup(frm) {
		frm.set_query("mode_of_payment", () => ({ filters: { enabled: 1 } }));
	},
	refresh(frm) {
        maintenance_rental_context(frm, "setup");
		if (frm.is_new()) return;
		if (frm.doc.status === "Completed" && frm.doc.cost > 0) {
			if (frm.doc.expense_entry) {
				frappe.db.get_value("Expense Entry", frm.doc.expense_entry, "docstatus").then(({ message }) => {
					if (!message || message.docstatus === 2) frm.trigger("add_expense_button");
				});
			} else {
				frm.trigger("add_expense_button");
			}
		}
	},
	add_expense_button(frm) {
			frm.add_custom_button(__("Create Expense"), () => {
				frappe.call({
						method: "heavy_equipment_rental.heavy_equipment_rental.doctype.crane_maintenance.crane_maintenance.create_expense",
						args: { maintenance: frm.doc.name },
					}).then(({ message }) => {
						frm.reload_doc();
						frappe.set_route("Form", "Expense Entry", message);
					});
			});
	},
});


async function maintenance_rental_context(frm, method) {
    if (frm._setting_rental_context) return;
    await frappe.require("/assets/heavy_equipment_rental/js/rental_context.js");
    return heavy_equipment_rental.rental_context[method](frm);
}
frappe.ui.form.on("Crane Maintenance", Object.fromEntries([
    "crane", "actual_start_date", "actual_end_date",
].map(field => [field, frm => maintenance_rental_context(frm, "changed")])));

frappe.ui.form.on("Crane Maintenance", {
    crane_assignment(frm) { return maintenance_rental_context(frm,"assignment_changed"); },
    crane_timesheet(frm) { return maintenance_rental_context(frm,"timesheet_changed"); },
});
