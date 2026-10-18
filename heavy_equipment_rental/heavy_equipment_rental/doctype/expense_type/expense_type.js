frappe.ui.form.on("Expense Type", {
	setup(frm) {
		frm.set_query("account", () => ({ filters: { root_type: "Expense", is_group: 0 } }));
	},
});
