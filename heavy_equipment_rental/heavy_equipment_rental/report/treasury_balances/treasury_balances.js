function renderTreasuryTrend(options) {
    this.chart?.destroy?.();
    const {treasury_accounts: accounts, currency, precision, title, ...chart} = options;
    if (!accounts) return frappe.views.QueryReport.prototype.render_chart.call(this, options);

    const panel = $("<section>").addClass("her-treasury-trend").css({
        padding: "0.9rem 1rem", border: "1px solid var(--border-color)",
        borderRadius: "var(--border-radius-md)",
    }).appendTo(this.$chart.empty().show());
    const header = $("<div>").css({
        display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "0.65rem",
    }).appendTo(panel);
    $("<h5>").addClass("mb-0").text(title).appendTo(header);
    const picker = $("<select>").addClass("form-control input-xs").css({width: "auto", maxWidth: "100%"})
        .attr("aria-label", __("Trend Account")).appendTo(header);
    $("<option>").val("").text(__("All Accounts")).appendTo(picker);
    accounts.forEach((account, index) => $("<option>").val(index).text(account.name).appendTo(picker));

    const plot = $("<div>").appendTo(panel);
    const dayLabels = chart.data.labels.map(day => {
        const [, month, date] = day.split("-");
        return date + "/" + month;
    });
    const dates = Object.fromEntries(dayLabels.map((label, index) => [label, chart.data.labels[index]]));
    const draw = () => {
        this.chart?.destroy?.();
        const selected = picker.val();
        const series = selected === "" ? chart.data.datasets[0] : accounts[Number(selected)];
        const dataset = {...series, name: frappe.utils.escape_html(series.name)};
        const data = {labels: dayLabels, datasets: [dataset]};
        this.chart = new frappe.Chart(plot[0], {
            ...chart, data,
            height: 250, animate: false, disableEntryAnimation: true,
            axisOptions: {...chart.axisOptions, xIsSeries: 1},
            tooltipOptions: {
                formatTooltipX: label => frappe.datetime.str_to_user(dates[label]),
                formatTooltipY: value => format_number(value, null, precision) + " " + currency,
            },
        });
        this.chart.update(data);
    };
    picker.on("change", draw);
    draw();
}

frappe.query_reports["Treasury Balances"] = {
    filters: [{
        fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
        reqd: 1, default: frappe.defaults.get_user_default("Company"),
    }],
    onload(report) {
        report.render_chart = renderTreasuryTrend;
    },
    after_datatable_render(datatable) {
        const table = $(datatable.datatableWrapper);
        if (table.children("style.her-treasury-balances-style").length) return;
        table.append(`<style class="her-treasury-balances-style">
            .datatable:has(.her-treasury-balance) .dt-scrollable .dt-row:nth-child(even) > .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
            }
            .datatable:has(.her-treasury-balance) .dt-scrollable .dt-row:is(:hover, :focus-within) > .dt-cell {
                --dt-cell-bg: color-mix(in srgb, var(--fg-color) 87%, var(--blue-500));
            }
        </style>`);
    },
    formatter(value, row, column, data, default_formatter) {
        if (column.fieldname === "payment_modes") {
            const modes = frappe.utils.escape_html(value || "—");
            return `<span title="${modes}">${modes}</span>`;
        }
        const formatted = default_formatter(value, row, column, data);
        if (column.fieldname !== "balance" || !data) return formatted;
        const color = value < 0 ? "text-danger" : value > 0 ? "text-success" : "text-muted";
        return `<strong class="her-treasury-balance ${color}">${formatted}</strong>`;
    },
};
