frappe.ui.form.on("Crane Maintenance", {
	refresh(frm) {
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
						method: "jimmy_cranes.jimmy_cranes.doctype.crane_maintenance.crane_maintenance.create_expense",
						args: { maintenance: frm.doc.name },
					}).then(({ message }) => {
						frm.reload_doc();
						frappe.set_route("Form", "Expense Entry", message);
					});
			});
	},
});
