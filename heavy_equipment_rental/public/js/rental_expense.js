frappe.ui.form.on("Expense Entry", {
    refresh(frm) {
        if (frm.is_new()) return frappe.new_doc("Grouped Expense");
        frm.disable_save();
        frappe.db.get_value("Grouped Expense", {legacy_expense: frm.doc.name}, "name").then(({message}) => {
            if (message?.name) frm.add_custom_button(__("Grouped Expense"), () =>
                frappe.set_route("Form", "Grouped Expense", message.name));
        });
    },
});
