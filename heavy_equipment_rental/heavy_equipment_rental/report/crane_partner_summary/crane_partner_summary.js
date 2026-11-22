frappe.query_reports["Crane Partner Summary"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
            on_change(report) {
                if (report._no_refresh) return;
                if (report.get_filter_value("shareholder")) report.set_filter_value("shareholder", "");
                else report.refresh();
            } },
        { fieldname: "report_date", label: __("Report Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
        { fieldname: "shareholder", label: __("Partner"), fieldtype: "Link", options: "Shareholder",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}}) },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
        { fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane" },
        { fieldname: "timesheet", label: __("Timesheet"), fieldtype: "Link", options: "Crane Timesheet" },
        { fieldname: "status", label: __("Entitlement Status"), fieldtype: "Select",
            options: ["", "Awaiting Invoice", "Draft", "Unpaid", "Partly Paid", "Paid", "No Entitlement"]
                .map(value => ({value, label: value ? __(value) : __("Entitlement Status")})) },
    ],
    async onload(report) {
        // Link titles can still be loading when a statement is opened from a filtered URL.
        const links = report.filters.filter(field =>
            field.df.fieldtype === "Link" && field.value && !field.df.hidden && !field.get_value());
        await Promise.all(links.map(field => field.set_link_title(field.value)));
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
        if (table.children("style.her-partner-summary-style").length) return;
        table.append(`<style class="her-partner-summary-style">
            .datatable:has(.her-partner-summary-name) .dt-scrollable .dt-row:nth-child(even) > .dt-cell {
                --dt-cell-bg: var(--subtle-accent);
            }
            .datatable:has(.her-partner-summary-name) .dt-scrollable .dt-row:is(:hover, :focus-within) > .dt-cell {
                --dt-cell-bg: color-mix(in srgb, var(--fg-color) 87%, var(--blue-500));
                background-color: var(--dt-cell-bg);
            }
            .datatable:has(.her-partner-summary-name) .dt-footer .dt-cell {
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
            return `<span class="her-partner-summary-name" title="${label}">${link}</span>`;
        }
        const currencyRow = column.fieldtype === "Currency" ? data || frappe.query_report.data[0] : data;
        const formatted = default_formatter(value, row, column, currencyRow);
        if (field !== "outstanding_amount" || !data?.party) return formatted;

        const filters = {...frappe.query_report.get_filter_values(), currency: data.currency};
        if (data.shareholder) {
            filters.shareholder = data.shareholder;
        } else {
            delete filters.shareholder;
            filters.partner_supplier = data.party;
        }
        const url = "/app/query-report/Crane%20Partner%20Statement" + frappe.utils.make_query_string(filters);
        const color = Number(value) > 0 ? "text-danger" : "text-primary";
        const title = frappe.utils.escape_html(__("View Partner Statement"));
        return `<a class="${color}" style="text-decoration:underline" href="${frappe.utils.escape_html(url)}"
            title="${title}">${formatted}</a>`;
    },
};
