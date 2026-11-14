// Keep confirmation and execution together for circular rental links.
for (const doctype of ["Sales Invoice", "Crane Timesheet", "Crane Profit Settlement", "Expense Entry"]) {
    frappe.ui.form.on(doctype, {
        setup(frm) {
            frm.savecancel = async function (btn, callback, on_error) {
                const args = { doctype: frm.doctype, name: frm.doc.name };
                let plan;
                try {
                    plan = await frappe.xcall("heavy_equipment_rental.cancellation.get_plan", args);
                } catch (error) {
                    frm.handle_save_fail(btn, on_error);
                    return;
                }
                const links = plan.map(row => `<li>${frappe.utils.escape_html(__(row.doctype))}: ${frappe.utils.get_form_link(row.doctype, row.name, true)}</li>`).join("");
                frappe.confirm(__("Cancel all of the following documents?") + `<ul>${links}</ul>` +
                    `<p class="text-danger">${__("This reverses the accounting for every listed document, including the full amount of any payment shared with other invoices or settlements. It does not recover money already paid. Cancelled documents remain in history; use Amend to create corrected replacements.")}</p>`, async () => {
                    try {
                        await frappe.call({
                            method: "heavy_equipment_rental.cancellation.cancel_all",
                            args: { ...args, confirmed_plan: JSON.stringify(plan) },
                            freeze: true,
                        });
                        await frm.reload_doc();
                        callback && callback();
                        frm.script_manager.trigger("after_cancel");
                    } catch (error) {
                        frm.handle_save_fail(btn, on_error);
                    }
                }, () => frm.handle_save_fail(btn, on_error));
            };
        },
    });
}
