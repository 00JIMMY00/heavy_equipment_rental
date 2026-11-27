async function show_treasury_account(frm, mode_field, account_field) {
	const doc = frm.doc;
	const { company } = doc;
	const mode_of_payment = doc[mode_field];
	await frm.set_value(account_field, null);
	if (!company || !mode_of_payment) return;

	const result = await frappe.xcall(
		"erpnext.accounts.doctype.sales_invoice.sales_invoice.get_bank_cash_account",
		{ mode_of_payment, company }
	);
	if (frm.doc === doc && doc.company === company && doc[mode_field] === mode_of_payment) {
		return frm.set_value(account_field, result.account);
	}
}

frappe.ui.form.on("Treasury Transaction", {
	setup(frm) {
		frm.set_query("cost_center", () => ({
			filters: {company: frm.doc.company, is_group: 0, disabled: 0},
		}));
		frm.set_query("party_type", () => ({
			query: "erpnext.setup.doctype.party_type.party_type.get_party_type",
		}));
		const payment_modes = () => ({
			query: "heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction.treasury_payment_mode_query",
			filters: { company: frm.doc.company },
		});
		frm.set_query("mode_of_payment", payment_modes);
		frm.set_query("destination_mode_of_payment", payment_modes);
	},
	party_type(frm) {
		frm.set_value("party", null);
	},
	company(frm) {
		return frm.set_value({
			cost_center: null,
			mode_of_payment: null,
			destination_mode_of_payment: null,
			source_account: null,
			destination_account: null,
		});
	},
	mode_of_payment(frm) {
		return show_treasury_account(frm, "mode_of_payment", "source_account");
	},
	destination_mode_of_payment(frm) {
		return show_treasury_account(frm, "destination_mode_of_payment", "destination_account");
	},
});
