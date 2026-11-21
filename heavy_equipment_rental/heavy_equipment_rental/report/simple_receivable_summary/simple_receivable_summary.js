frappe.query_reports["Simple Receivable Summary"] = {
    tree: true,
    initial_depth: 1,
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "report_date",
            label: __("Report Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
        {
            fieldname: "group_by",
            label: __("Group By"),
            fieldtype: "Select",
            options: [
                { value: "Customer", label: __("Customer") },
                { value: "Invoice", label: __("Invoice") },
                { value: "Customer Group", label: __("Customer Group") },
                { value: "Territory", label: __("Territory") },
            ],
            default: "Customer",
            reqd: 1,
        },
        { fieldname: "overdue_only", label: __("Overdue Only"), fieldtype: "Check" },
    ],

    onload(report) {
        if (!frappe.model.can_create("Payment Entry")) return;
        report.page.add_inner_button(__("Collect Selected Invoices"), () => {
            const checked = report.datatable ? report.get_checked_items() : [];
            const invoices = [...new Set(checked.flatMap((row) => row.invoice_names || [row.invoice]).filter(Boolean))];
            if (!invoices.length) {
                frappe.msgprint(__("Select one or more invoices for the same customer."));
                return;
            }
            this.collect(report, invoices);
        });
        $(report.page.wrapper)
            .off("click.her_receivable", "[data-her-receivable-invoices]")
            .on("click.her_receivable", "[data-her-receivable-invoices]", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const invoices = JSON.parse(decodeURIComponent(event.currentTarget.dataset.herReceivableInvoices));
                this.collect(report, invoices);
            });
    },

    get_datatable_options(options) {
        return { ...options, checkboxColumn: frappe.model.can_create("Payment Entry") };
    },

    async collect(report, invoices) {
        if (report.her_receivable_payment_pending) return;
        report.her_receivable_payment_pending = true;
        try {
            const response = await frappe.call({
                method: "heavy_equipment_rental.receivable_payments.make_payment_entry",
                args: { invoices },
                freeze: true,
                freeze_message: __("Preparing Payment Entry"),
            }).catch(() => null);
            if (response?.message) {
                await frappe.model.with_doctype("Payment Entry");
                const [payment] = frappe.model.sync(response.message);
                frappe.set_route("Form", "Payment Entry", payment.name);
            }
        } finally {
            report.her_receivable_payment_pending = false;
        }
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);
        if (column.fieldname === "payment") {
            if (!frappe.model.can_create("Payment Entry") || (data.is_group && !data.customer)) return "";
            const invoices = data.invoice_names || [data.invoice];
            const encoded = frappe.utils.escape_html(encodeURIComponent(JSON.stringify(invoices)));
            const label = data.is_group ? __("Collect from Customer") : __("Collect Payment");
            return `<button type="button" class="btn btn-xs btn-primary" data-her-receivable-invoices="${encoded}">${label}</button>`;
        }
        const formatted = column.fieldname === "label"
            ? frappe.utils.escape_html(value || "")
            : default_formatter(value, row, column, data);
        if (data.is_group) return `<strong>${formatted || ""}</strong>`;
        if (column.fieldname === "paid") return `<span class="text-success">${formatted}</span>`;
        if (["outstanding", "days_overdue", "status"].includes(column.fieldname)) {
            const color = data.days_overdue > 0 ? "text-danger" : "text-warning";
            return `<span class="${color}">${formatted}</span>`;
        }
        return formatted;
    },
};
