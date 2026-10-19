frappe.ui.form.on("Expense Entry", {
	setup(frm) {
		frm.set_query("crane", () => ({
			query: "heavy_equipment_rental.heavy_equipment_rental.doctype.expense_entry.expense_entry.project_crane_query",
			filters: { project: frm.doc.project },
		}));
		frm.set_query("employee", () => ({
			query: "heavy_equipment_rental.heavy_equipment_rental.doctype.expense_entry.expense_entry.driver_employee_query",
		}));
		frm.set_query("mode_of_payment", () => ({ filters: { enabled: 1 } }));
	},
	project(frm) {
		frm.set_value("crane", null);
	},
});
