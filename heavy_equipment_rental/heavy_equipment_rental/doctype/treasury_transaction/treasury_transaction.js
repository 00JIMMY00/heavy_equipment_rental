frappe.ui.form.on("Treasury Transaction", {
	setup(frm) {
		frm.set_query("mode_of_payment", () => ({ filters: { enabled: 1 } }));
		frm.set_query("destination_account", () => ({
			filters: {
				company: frm.doc.company,
				is_group: 0,
				disabled: 0,
				account_type: ["in", ["Cash", "Bank"]],
				account_currency: frm.doc.currency,
				name: ["!=", frm.doc.source_account || ""],
			},
		}));
	},
	company(frm) {
		frm.set_value("destination_account", null);
		frm.set_value("source_account", null);
		frm.set_value("currency", null);
		if (frm.doc.company) {
			frappe.db.get_value("Company", frm.doc.company, "default_currency", (r) => {
				frm.set_value("currency", r.default_currency);
			});
		}
		frm.trigger("mode_of_payment");
	},
	mode_of_payment(frm) {
		frm.set_value("source_account", null);
		if (frm.doc.company && frm.doc.mode_of_payment) {
			frappe.call({
				method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.get_bank_cash_account",
				args: { mode_of_payment: frm.doc.mode_of_payment, company: frm.doc.company },
				callback(r) {
					frm.set_value("source_account", r.message?.account || null);
				},
			});
		}
	},
});
