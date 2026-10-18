frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (
			frm.doc.docstatus !== 1 ||
			!frm.doc.customer_pays_drivers_directly ||
			frm.doc.driver_direct_payment_journal_entry ||
			!frappe.model.can_create("Journal Entry")
		) return;
		frm.add_custom_button(__("Record Customer Payment to Drivers"), () => {
			frappe.prompt([
				{ fieldname: "payment_date", fieldtype: "Date", label: __("Actual Payment Date"), default: frappe.datetime.get_today(), reqd: 1 },
				{ fieldname: "reference", fieldtype: "Data", label: __("Payment Reference or Proof"), reqd: 1 },
			], (values) => frappe.call({
				method: "heavy_equipment_rental.billing.record_direct_driver_payment",
				args: { invoice_name: frm.doc.name, ...values },
				freeze: true,
				callback: () => frm.reload_doc(),
			}), __("Record Customer Payment to Drivers"));
		}, __("Actions"));
	},
});
