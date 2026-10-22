frappe.ui.form.on("Expense Entry", {
	setup(frm) {
		frm.set_query("mode_of_payment", () => ({ filters: { enabled: 1 } }));
	},
});
