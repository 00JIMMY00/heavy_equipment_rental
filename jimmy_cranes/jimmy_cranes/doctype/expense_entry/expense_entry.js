frappe.ui.form.on("Expense Entry", {
	setup(frm) {
		frm.set_query("crane", () => ({
			query: "jimmy_cranes.jimmy_cranes.doctype.expense_entry.expense_entry.project_crane_query",
			filters: { project: frm.doc.project },
		}));
		frm.set_query("employee", () => ({
			query: "jimmy_cranes.jimmy_cranes.doctype.expense_entry.expense_entry.driver_employee_query",
		}));
	},
	project(frm) {
		frm.set_value("crane", null);
	},
});
