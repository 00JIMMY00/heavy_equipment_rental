const partnerMovementAmounts = [
    ["entitlement", "Posted Entitlement"],
    ["pending_entitlement", "Pending Entitlement"],
    ["paid_amount", "Paid / Adjusted"],
    ["outstanding_amount", "Outstanding"],
];

function renderPartnerAging(options) {
    for (const tip of this.partnerAgingTooltips || []) tip.dispose();
    this.partnerAgingTooltips = [];
    this.chart?.destroy?.();
    this.partnerAgingDonut?.destroy?.();
    this.partnerAgingDonut = null;
    const {partner_aging: donut, currency, ...bar} = options;
    if (!donut) return frappe.views.QueryReport.prototype.render_chart.call(this, options);

    const charts = $("<div>").addClass("her-partner-aging").css({
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 340px), 1fr))",
        gap: "1rem",
    }).appendTo(this.$chart.empty().show());
    const currencyPrecision = frappe.boot.sysdefaults.currency_precision;
    const precision = currencyPrecision === "" || currencyPrecision == null ? 2 : cint(currencyPrecision);
    const amount = value => format_number(value, null, precision) + " " + currency;

    const panel = ({title, ...chart}) => {
        const card = $("<section>").css({
            minWidth: 0, padding: "0.75rem 1rem", border: "1px solid var(--border-color)",
            borderRadius: "var(--border-radius-md)",
        }).appendTo(charts);
        $("<h5>").text(title).appendTo(card);
        const plot = $("<div>").appendTo(card);
        return {
            card,
            chart: new frappe.Chart(plot[0], {
                ...chart, height: 220, disableEntryAnimation: true,
                axisOptions: {...chart.axisOptions, xIsSeries: 1},
                tooltipOptions: {formatTooltipX: label => frappe.utils.escape_html(label), formatTooltipY: amount},
            }),
        };
    };

    this.chart = panel(bar).chart;
    const aging = panel(donut);
    this.partnerAgingDonut = aging.chart;
    const legend = $("<div>").css({display: "flex", flexWrap: "wrap", gap: "0.5rem 1rem"}).appendTo(aging.card);
    donut.data.labels.forEach((label, index) => {
        const item = $("<span>").addClass("small").css({
            display: "inline-flex", alignItems: "center", gap: "0.4rem", maxWidth: "100%",
        }).appendTo(legend);
        $("<span>").attr("aria-hidden", "true").css({
            width: "0.6rem", height: "0.6rem", flexShrink: 0, borderRadius: "2px", backgroundColor: donut.colors[index],
        }).appendTo(item);
        $("<span>").text(label + " · " + amount(donut.data.datasets[0].values[index])).appendTo(item);
    });
    const help = $('<button type="button">').addClass("btn btn-default btn-xs")
        .attr("aria-label", __("How is age calculated?"))
        .css({padding: 0, width: "1.25rem", height: "1.25rem", fontStyle: "italic", borderRadius: "50%"})
        .text("i").appendTo(legend)
        .tooltip({
            title: __("Age counts days from the settlement posting date to the report date."),
            container: charts[0], boundary: "viewport", trigger: "hover focus", placement: "top", animation: false,
        }).on("click", () => help.tooltip("show"))
        .on("keydown", event => {
            if (event.key === "Escape") help.tooltip("hide");
        });
    this.partnerAgingTooltips.push(help.data("bs.tooltip"));
}

function openPartnerMovements(report, source) {
    const movements = report.data.filter(row => row.settlement === source.settlement &&
        row.party_type === source.party_type && row.party === source.party);
    const dialog = new frappe.ui.Dialog({
        title: __("Settlement Movements"),
        size: "extra-large",
        fields: [{fieldtype: "HTML", fieldname: "partner_movements"}],
    });
    const content = $(dialog.fields_dict.partner_movements.wrapper);
    const heading = $("<p>").addClass("font-weight-bold").text((source.partner_name || source.party) + " · ");
    $("<a>").attr("href", frappe.utils.get_form_link("Crane Profit Settlement", source.settlement))
        .text(source.settlement).appendTo(heading);
    heading.appendTo(content);
    $("<p>").addClass("text-muted").text(__("As of {0}", [
        frappe.datetime.str_to_user(report.get_filter_value("report_date")),
    ])).appendTo(content);
    const table = $('<table class="table table-sm">').appendTo($('<div class="table-responsive">').appendTo(content));
    const header = $("<tr>").appendTo($("<thead>").appendTo(table));
    ["Posting Date", "Movement", "Voucher", ...partnerMovementAmounts.map(([, label]) => label)].forEach(label => {
        $('<th scope="col">').text(__(label)).appendTo(header);
    });
    const body = $("<tbody>").appendTo(table);
    movements.forEach(movement => {
        const row = $("<tr>").appendTo(body);
        $("<td>").text(frappe.datetime.str_to_user(movement.posting_date)).appendTo(row);
        $("<td>").text(movement.movement_type).appendTo(row);
        $("<a>").attr("href", frappe.utils.get_form_link(movement.voucher_type, movement.voucher_no))
            .text(movement.voucher_no).appendTo($("<td>").appendTo(row));
        partnerMovementAmounts.forEach(([field]) => {
            const value = movement[field];
            $("<td>").text(value == null ? "" : format_currency(value, movement.currency)).appendTo(row);
        });
    });
    dialog.show();
}

frappe.query_reports["Crane Partner Statement"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
            on_change(report) {
                if (report._no_refresh) return;
                if (report.get_filter_value("shareholder")) report.set_filter_value("shareholder", "");
                else report.refresh();
            } },
        { fieldname: "report_date", label: __("Report Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
        { fieldname: "shareholder", label: __("Partner"), fieldtype: "Link", options: "Shareholder",
            get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }) },
        { fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane" },
        { fieldname: "timesheet", label: __("Timesheet"), fieldtype: "Link", options: "Crane Timesheet" },
        { fieldname: "status", label: __("Entitlement Status"), fieldtype: "Select",
            options: ["", "Awaiting Invoice", "Draft", "Unpaid", "Partly Paid", "Paid", "No Entitlement"]
                .map(value => ({value, label: value ? __(value) : __("Entitlement Status")})) },
        { fieldname: "currency", label: __("Currency"), fieldtype: "Link", options: "Currency" },
        { fieldname: "partner_supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier", hidden: 1 },
    ],
    async onload(report) {
        // Link titles can still be loading when a statement is opened from a filtered URL.
        const links = report.filters.filter(field =>
            field.df.fieldtype === "Link" && field.value && !field.df.hidden && !field.get_value());
        await Promise.all(links.map(field => field.set_link_title(field.value)));
        report.render_chart = renderPartnerAging;
        $(report.page.wrapper).off("click.herPartnerMovements", "[data-partner-movement]")
            .on("click.herPartnerMovements", "[data-partner-movement]", event => {
                event.stopPropagation();
                const row = report.datatable.datamanager.getData(Number(event.currentTarget.dataset.partnerMovement));
                if (row) openPartnerMovements(report, row);
            });
    },
    get_datatable_options(options) {
        return {
            ...options,
            hooks: {
                ...options.hooks,
                columnTotal(values, cell) {
                    if (cell.column.fieldname === "partner_name") return __("Total");
                    return frappe.utils.report_column_total(values, cell);
                },
            },
        };
    },
    after_datatable_render(datatable) {
        const table = $(datatable.datatableWrapper);
        if (table.children("style.her-partner-statement-style").length) return;
        table.append(`<style class="her-partner-statement-style">
            .datatable:has(.her-partner-name) .dt-scrollable .dt-row:nth-child(even) > .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
            }
            .datatable:has(.her-partner-name) .dt-scrollable .dt-row:is(:hover, :focus-within) > .dt-cell {
                --dt-cell-bg: color-mix(in srgb, var(--fg-color) 87%, var(--blue-500));
                background-color: var(--dt-cell-bg);
            }
            .datatable:has(.her-partner-name) .dt-footer .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
                border-top-color: var(--dark-border-color);
                font-weight: 600;
            }
        </style>`);
    },
    formatter(value, row, column, data, default_formatter) {
        const field = column.fieldname;
        if (field === "partner_name") {
            const label = frappe.utils.escape_html(value || data?.party || "");
            if (!data?.party) return label;
            const link = data.shareholder
                ? frappe.utils.get_form_link("Shareholder", data.shareholder, true, label)
                : frappe.utils.get_form_link(data.party_type, data.party, true, label);
            return `<span class="her-partner-name" title="${label}">${link}</span>`;
        }
        const currencyRow = column.fieldtype === "Currency" ? data || frappe.query_report.data[0] : data;
        const formatted = default_formatter(value, row, column, currencyRow);
        if (field === "status" && data?.status) {
            const color = {Paid: "green", "Partly Paid": "orange", Unpaid: "red"}[data.status] || "gray";
            return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.status))}</span>`;
        }
        if (value && row?.meta && partnerMovementAmounts.some(([key]) => key === field)) {
            const color = field === "paid_amount" ? "text-success"
                : field === "outstanding_amount" && Number(value) > 0 ? "text-danger" : "text-primary";
            return `<button type="button" class="btn btn-link btn-xs p-0 ${color}" style="text-decoration:underline"
                data-partner-movement="${row.meta.rowIndex}">${formatted}</button>`;
        }
        return formatted;
    },
};
