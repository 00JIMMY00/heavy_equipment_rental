frappe.provide("heavy_equipment_rental");

heavy_equipment_rental.create_supplier_payment = async function (frm) {
    if (frm.is_dirty()) {
        frappe.throw(__("Save your changes before creating a Payment."));
    }
    const args = { source_doctype: frm.doctype, source_name: frm.doc.name };
    const { message: invoices } = await frappe.call({
        method: "heavy_equipment_rental.purchasing.supplier_payment_invoices", args,
    });
    if (!invoices?.length) {
        frappe.msgprint(__("No unpaid submitted Purchase Invoices are linked to this record."));
        return;
    }
    const create = async (purchase_invoice) => {
        const { message } = await frappe.call({
            method: "heavy_equipment_rental.purchasing.make_supplier_payment",
            args: { ...args, purchase_invoice }, freeze: true,
        });
        if (message) {
            const [payment] = frappe.model.sync(message);
            frappe.set_route("Form", payment.doctype, payment.name);
        }
    };
    if (invoices.length === 1) return create(invoices[0].name);
    frappe.prompt([{
        fieldname: "purchase_invoice", fieldtype: "Select", label: __("Purchase Invoice"), reqd: 1,
        options: invoices.map(row => ({ value: row.name,
            label: `${row.name} · ${row.supplier} · ${format_currency(row.outstanding_amount, row.currency)}` })),
    }], values => create(values.purchase_invoice), __("Create Supplier Payment"), __("Create Payment"));
};
