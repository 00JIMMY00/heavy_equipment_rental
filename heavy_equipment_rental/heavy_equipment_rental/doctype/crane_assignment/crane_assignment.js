frappe.ui.form.on("Crane Assignment", {
    refresh(frm) {
        if (frm.is_new()) return;
        if (frappe.model.can_create("Expense Entry"))
            frm.add_custom_button(__("Expense"), () =>
                frappe.new_doc("Expense Entry", { crane_assignment: frm.doc.name }), __("Create"));
        frm.add_custom_button(__("New Timesheet"), () => {
            frappe.new_doc("Crane Timesheet", {
                assignment: frm.doc.name,
                customer: frm.doc.customer,
                location: frm.doc.location,
                crane: frm.doc.assigned_cranes?.length === 1 ? frm.doc.assigned_cranes[0].crane : null,
            });
        }, __("Create"));
        frm.add_custom_button(__("Timesheets"), () =>
            frappe.set_route("List", "Crane Timesheet", { assignment: frm.doc.name }), __("View"));
        if (frappe.model.can_create("Sales Invoice")) {
            frm.add_custom_button(__("Generate Sales Invoice"), () => frappe.call({
                method: "heavy_equipment_rental.billing.generate_sales_invoice",
                args: { assignment: frm.doc.name },
                freeze: true,
                callback: ({ message }) => {
                    if (message?.name) frappe.set_route("Form", "Sales Invoice", message.name);
                    else if (message?.already_exists) frappe.msgprint(__("All submitted work is already billed."));
                },
            }), __("Create"));
        }
        frm.add_custom_button(__("Resource Timeline"), () => {
            window.location.href = `/rental-calendar/timeline?assignment=${encodeURIComponent(frm.doc.name)}`;
        }, __("View"));
    },
});
