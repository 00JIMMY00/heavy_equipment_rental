function renderSalaryCharts(options) {
    for (const tooltip of this.salaryChartTooltips || []) tooltip.dispose();
    const tooltips = this.salaryChartTooltips = [];
    this.chart?.destroy?.();
    this.salaryWithdrawalDonut?.destroy();
    this.salaryWithdrawalDonut = null;
    const {withdrawal_breakdown: donut, legend_help, currency, precision, ...bar} = options;
    if (!donut) return frappe.views.QueryReport.prototype.render_chart.call(this, options);

    const charts = $("<div>").addClass("salary-withdrawal-charts").css({
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 340px), 1fr))",
        gap: "1rem",
    }).appendTo(this.$chart.empty().show());

    const formatAmount = amount => format_number(amount, null, precision) + " " + currency;
    const chartSettings = {height: 220, disableEntryAnimation: true, tooltipOptions: {formatTooltipY: formatAmount}};

    const panel = (title) => {
        const card = $("<section>").css({
            minWidth: 0, padding: "0.75rem 1rem", border: "1px solid var(--border-color)",
            borderRadius: "var(--border-radius-md)",
        }).appendTo(charts);
        $("<h5>").text(title).appendTo(card);
        const plot = $("<div>").appendTo(card);
        const legend = $("<div>").css({display: "flex", flexWrap: "wrap", gap: "0.5rem 1rem"}).appendTo(card);
        return {plot, legend};
    };

    const addLegend = (legend, items, colors) => {
        items.forEach(({label, amount}, index) => {
            const item = $("<span>").addClass("small").css({
                display: "inline-flex", alignItems: "center", gap: "0.4rem", maxWidth: "100%",
            }).appendTo(legend);
            $("<span>").attr("aria-hidden", "true").css({
                width: "0.6rem", height: "0.6rem", flexShrink: 0, borderRadius: "2px", backgroundColor: colors[index],
            }).appendTo(item);
            $("<span>").text(label + " · " + formatAmount(amount)).appendTo(item);
            const info = $('<button type="button">').addClass("btn btn-default btn-xs")
                .attr("aria-label", __("What does {0} mean?", [label]))
                .css({
                    flexShrink: 0, padding: 0, width: "1.25rem", height: "1.25rem",
                    fontStyle: "italic", borderRadius: "50%",
                }).text("i").appendTo(item)
                .tooltip({title: legend_help?.[label], container: charts[0], boundary: "viewport",
                    trigger: "hover focus", placement: "top", animation: false})
                .on("click", event => $(event.currentTarget).tooltip("show"))
                .on("keydown", event => {
                    if (event.key === "Escape") $(event.currentTarget).tooltip("hide");
                });
            tooltips.push(info.data("bs.tooltip"));
        });
    };

    const salary = panel(__("Earned Salary and Withdrawals"));
    const withdrawals = panel(__("Withdrawal Breakdown"));
    const barItems = bar.data.datasets.map(dataset => ({label: dataset.name, amount: Math.max(...dataset.values)}));
    const donutItems = donut.data.labels.map((label, index) => ({label, amount: donut.data.datasets[0].values[index]}));
    this.chart = null;
    if (barItems.some(item => item.amount > 0)) {
        this.chart = new frappe.Chart(salary.plot[0], {...bar, ...chartSettings});
        addLegend(salary.legend, barItems, bar.colors);
    } else {
        $("<p>").addClass("text-muted").text(__("No salary activity for this period.")).appendTo(salary.plot);
    }
    if (donutItems.some(item => item.amount > 0)) {
        this.salaryWithdrawalDonut = new frappe.Chart(withdrawals.plot[0], {...donut, ...chartSettings});
        addLegend(withdrawals.legend, donutItems, donut.colors);
    } else {
        $("<p>").addClass("text-muted").text(__("No salary withdrawals for this period.")).appendTo(withdrawals.plot);
    }
}

frappe.query_reports["Employee Salary Withdrawals"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
            reqd: 1, default: frappe.defaults.get_user_default("Company"),
            on_change(report) {
                if (report.get_filter_value("employee")) report.set_filter_value("employee", "");
                else report.refresh();
            }},
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1,
            default: frappe.datetime.month_start()},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1,
            default: frappe.datetime.month_end()},
        {fieldname: "show_drafts", label: __("Show Drafts"), fieldtype: "Check", default: 0},
    ],
    onload(report) {
        report.render_chart = renderSalaryCharts;
        $(report.page.wrapper).off("click.herSalary", "[data-salary-employee]")
            .on("click.herSalary", "[data-salary-employee]", async event => {
                event.stopPropagation();
                const button = event.currentTarget;
                button.disabled = true;
                try {
                    const payment = await frappe.xcall(
                        "heavy_equipment_rental.heavy_equipment_rental.report.employee_salary_withdrawals.employee_salary_withdrawals.prepare_salary_payment",
                        {company: report.get_filter_value("company"), employee: button.dataset.salaryEmployee});
                    await frappe.model.with_doctype("Grouped Expense");
                    const [doc] = frappe.model.sync(payment);
                    await frappe.set_route("Form", doc.doctype, doc.name);
                } finally {
                    button.disabled = false;
                }
            });
    },
    get_datatable_options(options) {
        return {
            ...options,
            hooks: {
                ...options.hooks,
                columnTotal(values, cell) {
                    if (cell.column.fieldname === "employee_name") return __("Total");
                    return frappe.utils.report_column_total(values, cell);
                },
            },
        };
    },
    after_datatable_render(datatable) {
        const table = $(datatable.datatableWrapper);
        if (table.children("style.her-salary-table-style").length) return;
        table.append(`<style class="her-salary-table-style">
            .datatable:has(.her-salary-employee) .dt-scrollable .dt-row:nth-child(even) > .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
            }
            .datatable:has(.her-salary-employee) .dt-scrollable .dt-row:is(:hover, :focus-within) > .dt-cell {
                --dt-cell-bg: color-mix(in srgb, var(--fg-color) 87%, var(--blue-500));
            }
            .datatable:has(.her-salary-employee) .dt-footer .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
                border-top-color: var(--dark-border-color);
                font-weight: 600;
            }
        </style>`);
    },
    formatter(value, row, column, data, default_formatter) {
        const field = column.fieldname;
        if (field === "payment" && data?.employee) {
            const employee = frappe.utils.escape_html(data.employee);
            return `<button type="button" class="btn btn-xs btn-primary" data-salary-employee="${employee}">${__("Pay Salary / Advance")}</button>`;
        }
        if (field === "employee_name") {
            const name = frappe.utils.escape_html(value || "");
            if (!data?.employee) return name;
            const link = frappe.utils.get_form_link("Employee", data.employee, true, name);
            return `<span class="her-salary-employee">${link}</span>`;
        }
        const currencyRow = column.fieldtype === "Currency" ? data || frappe.query_report.data[0] : data;
        const formatted = default_formatter(value, row, column, currencyRow);
        if (column.fieldtype !== "Currency") return formatted;
        let color = "text-muted";
        if (field === "balance") color = value > 0 ? "text-success" : value < 0 ? "text-danger" : "text-muted";
        else if (field === "posted_earned") color = "text-success";
        else if (["paid", "linked_paid", "standalone_paid"].includes(field)) color = "text-primary";
        return `<span class="${color}">${formatted}</span>`;
    },
};
