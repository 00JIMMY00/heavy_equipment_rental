const receivableAmountLabels = {
    invoiced: "Invoice Total",
    paid: "Total Paid",
    credit_note: "Credit Note",
    outstanding: "Outstanding Amount",
    overdue: "Overdue Amount",
};

function renderReceivableCharts(options) {
    for (const tooltip of this.receivableChartTooltips || []) tooltip.dispose();
    this.receivableChartTooltips = [];
    this.chart?.destroy?.();
    this.receivableDonut?.destroy?.();
    this.receivableDonut = null;
    const {receivable_breakdown: donut, currency, precision, ...bar} = options;
    if (!donut) return frappe.views.QueryReport.prototype.render_chart.call(this, options);

    const charts = $("<div>").addClass("her-receivable-charts").css({
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 340px), 1fr))",
        gap: "1rem",
    }).appendTo(this.$chart.empty().show());
    charts.append(`<style>
        .report-summary:has(~ .chart-wrapper .her-receivable-charts) {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.75rem;
        }
        .report-summary:has(~ .chart-wrapper .her-receivable-charts) .summary-item {
            margin: 0;
            min-width: 0;
            max-width: none;
        }
        @media (max-width: 1100px) {
            .report-summary:has(~ .chart-wrapper .her-receivable-charts) {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
        }
        @media (max-width: 620px) {
            .report-summary:has(~ .chart-wrapper .her-receivable-charts) {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
    </style>`);
    const amount = value => format_number(value, null, precision) + " " + currency;
    const descriptions = [
        __("Open invoice balances whose due date has not passed as of the report date."),
        __("Open invoice balances whose due date has passed as of the report date."),
    ];
    const render = ({title, ...chart}, legend = false) => {
        const panel = $("<section>").css({
            minWidth: 0, padding: "0.75rem 1rem", border: "1px solid var(--border-color)",
            borderRadius: "var(--border-radius-md)",
        }).appendTo(charts);
        $("<h5>").text(title).appendTo(panel);
        const plot = $("<div>").appendTo(panel);
        const instance = new frappe.Chart(plot[0], {
            ...chart, height: 220, disableEntryAnimation: true,
            axisOptions: {...chart.axisOptions, xIsSeries: 1},
            tooltipOptions: {formatTooltipX: label => frappe.utils.escape_html(label), formatTooltipY: amount},
        });
        if (legend) {
            const items = $("<div>").css({display: "flex", flexWrap: "wrap", gap: "0.5rem 1rem"}).appendTo(panel);
            chart.data.labels.forEach((label, index) => {
                const item = $("<span>").addClass("small").css({
                    display: "inline-flex", alignItems: "center", flexWrap: "wrap", gap: "0.4rem",
                }).appendTo(items);
                $("<span>").attr("aria-hidden", "true").css({
                    width: "0.6rem", height: "0.6rem", borderRadius: "2px", backgroundColor: chart.colors[index],
                }).appendTo(item);
                $("<span>").text(label + " · " + amount(chart.data.datasets[0].values[index])).appendTo(item);
                const info = $('<button type="button">').addClass("btn btn-default btn-xs")
                    .attr("aria-label", __("What does {0} mean?", [label]))
                    .css({padding: 0, width: "1.25rem", height: "1.25rem", fontStyle: "italic", borderRadius: "50%"})
                    .text("i").appendTo(item)
                    .tooltip({title: descriptions[index], container: charts[0], boundary: "viewport",
                        trigger: "hover focus", placement: "top", animation: false})
                    .on("click", () => info.tooltip("show"))
                    .on("keydown", event => {
                        if (event.key === "Escape") info.tooltip("hide");
                    });
                this.receivableChartTooltips.push(info.data("bs.tooltip"));
            });
        }
        return instance;
    };
    this.chart = render(bar);
    this.receivableDonut = render(donut, true);
}

function showReceivableBreakdown(report, source, field) {
    const invoiceNames = new Set(source.invoice_names || [source.invoice]);
    const invoices = report.data.filter(row => !row.is_group && invoiceNames.has(row.invoice));
    const dialog = new frappe.ui.Dialog({
        title: __(receivableAmountLabels[field]),
        size: "extra-large",
        fields: [{fieldtype: "HTML", fieldname: "receivable_details"}],
    });
    const content = $(dialog.fields_dict.receivable_details.wrapper);
    const money = value => format_currency(value, source.currency);
    $("<p>").addClass("font-weight-bold").text(source.label + " · " + money(source[field])).appendTo(content);
    $("<p>").addClass("text-muted").text(__("As of {0}", [
        frappe.datetime.str_to_user(report.get_filter_value("report_date")),
    ])).appendTo(content);

    const table = $('<table class="table table-sm">').appendTo($('<div class="table-responsive">').appendTo(content));
    const headings = $("<tr>").appendTo($("<thead>").appendTo(table));
    const fields = ["invoiced", "paid", "credit_note", "outstanding", "overdue"];
    ["Sales Invoice", "Due Date", ...fields.map(key => receivableAmountLabels[key])].forEach(label => {
        $('<th scope="col">').text(__(label)).appendTo(headings);
    });
    const body = $("<tbody>").appendTo(table);
    (field === "overdue" ? invoices.filter(row => row.overdue > 0) : invoices).forEach(invoice => {
        const row = $("<tr>").appendTo(body);
        $("<a>").attr("href", frappe.utils.get_form_link("Sales Invoice", invoice.invoice))
            .text(invoice.invoice).appendTo($("<td>").appendTo(row));
        $("<td>").text(frappe.datetime.str_to_user(invoice.due_date || invoice.posting_date)).appendTo(row);
        fields.forEach(key => $("<td>").toggleClass("font-weight-bold", key === field)
            .text(money(invoice[key])).appendTo(row));
    });
    dialog.show();
}

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
        {fieldname: "due_status", label: __("Due Status"), fieldtype: "Select", options: [
            {value: "", label: __("Due Status")},
            {value: "All", label: __("All")},
            {value: "Overdue", label: __("Overdue")},
            {value: "Not Due", label: __("Not Due")},
        ]},
        {fieldname: "overdue_only", label: __("Overdue Only"), fieldtype: "Check", hidden: 1},
    ],

    onload(report) {
        report.render_chart = renderReceivableCharts;
        $(report.page.wrapper).off("click.herReceivableDetails", "[data-receivable-row]")
            .on("click.herReceivableDetails", "[data-receivable-row]", event => {
                event.stopPropagation();
                const {receivableRow, receivableField} = event.currentTarget.dataset;
                const source = report.datatable.datamanager.getData(Number(receivableRow));
                if (source) showReceivableBreakdown(report, source, receivableField);
            });
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
        return {
            ...options, checkboxColumn: frappe.model.can_create("Payment Entry"), showTotalRow: true,
            hooks: {
                ...options.hooks,
                columnTotal(_values, cell) {
                    const field = cell.column.fieldname;
                    if (field === "label") return __("Report Total");
                    if (!receivableAmountLabels[field]) return "";
                    return frappe.query_report.data.reduce((total, row) => total + (row.is_group ? 0 : flt(row[field])), 0);
                },
            },
        };
    },

    after_datatable_render(datatable) {
        const table = $(datatable.datatableWrapper);
        if (table.children("style.her-receivable-style").length) return;
        table.append(`<style class="her-receivable-style">
            .datatable:has(.her-receivable-name) .dt-scrollable .dt-row:nth-child(even) > .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
            }
            .datatable:has(.her-receivable-name) .dt-scrollable .dt-row:is(:hover, :focus-within) > .dt-cell {
                --dt-cell-bg: color-mix(in srgb, var(--fg-color) 87%, var(--blue-500));
            }
            .datatable:has(.her-receivable-name) .dt-footer .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
                border-top-color: var(--dark-border-color);
                font-weight: 600;
            }
        </style>`);
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
        const field = column.fieldname;
        if (!data) {
            const currencyRow = column.fieldtype === "Currency" ? frappe.query_report.data[0] : null;
            return default_formatter(value, row, column, currencyRow);
        }
        if (column.fieldname === "payment") {
            if (!frappe.model.can_create("Payment Entry") || (data.is_group && !data.customer)) return "";
            const invoices = data.invoice_names || [data.invoice];
            const encoded = frappe.utils.escape_html(encodeURIComponent(JSON.stringify(invoices)));
            const label = __("Collect Payment");
            return `<button type="button" class="btn btn-xs btn-primary" data-her-receivable-invoices="${encoded}">${label}</button>`;
        }
        if (field === "label") {
            const name = frappe.utils.escape_html(value || "");
            const formatted = data.customer ? frappe.utils.get_form_link("Customer", data.customer, true, name) : name;
            return `<span class="her-receivable-name ${data.is_group ? "font-weight-bold" : ""}">${formatted}</span>`;
        }
        const formatted = default_formatter(value, row, column, data);
        const overdue = data.is_group ? data.overdue > 0 : data.days_overdue > 0;
        if (value && receivableAmountLabels[field] && row?.meta) {
            const color = field === "paid" ? "text-success" : field === "overdue" ? "text-danger" : "text-primary";
            return `<button type="button" class="btn btn-link btn-xs p-0 ${color} ${data.is_group ? "font-weight-bold" : ""}"
                style="text-decoration:underline" data-receivable-row="${row.meta.rowIndex}"
                data-receivable-field="${field}">${formatted}</button>`;
        }
        if (value && ["days_overdue", "status"].includes(field)) {
            return `<span class="${overdue ? "text-danger" : "text-success"}">${formatted}</span>`;
        }
        return data.is_group ? `<strong>${formatted || ""}</strong>` : formatted;
    },
};
