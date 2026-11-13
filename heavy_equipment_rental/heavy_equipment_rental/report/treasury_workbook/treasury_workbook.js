async function her_apply_treasury_filters(report, values) {
    const wasNoRefresh = report._no_refresh;
    report._no_refresh = true;
    report.her_setting_defaults = true;
    try {
        for (const [key, value] of Object.entries(values)) {
            const filter = report.get_filter(key);
            if (filter) await filter.set_value(value);
        }
    } finally {
        report.her_setting_defaults = false;
        report._no_refresh = wasNoRefresh;
    }
}

frappe.query_reports["Treasury Workbook"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
            default: frappe.defaults.get_user_default("Company"), reqd: 1,
            on_change: async () => {
                const report = frappe.query_report;
                if (report.her_setting_defaults || report._no_refresh) return;
                const company = report.get_filter_value("company");
                const r = await frappe.call({method: "heavy_equipment_rental.heavy_equipment_rental.report.treasury_workbook.treasury_workbook.get_defaults", args: {company}});
                if (company !== report.get_filter_value("company")) return;
                await her_apply_treasury_filters(report, {...(r.message || {account: "", batch: ""}), cost_center: ""});
                if (company && report.get_filter_value("account")) await report.refresh(true);
            }},
        {fieldname: "account", label: __("Treasury / Custody Account"), fieldtype: "Link", options: "Account", reqd: 1,
            get_query: () => ({query: "heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.treasury_transaction.treasury_account_query",
                filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "cost_center", label: __("Cost Center"), fieldtype: "Link", options: "Cost Center",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company"), is_group: 0, disabled: 0}})},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.year_start(), reqd: 1},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.year_end(), reqd: 1},
        {fieldname: "batch", label: __("Treasury Workbook Batch"), fieldtype: "Data"},
        {fieldname: "workbook_order", label: __("Workbook Order"), fieldtype: "Check", default: 1},
    ],
    get_datatable_options(options) {
        return Object.assign(options, {serialNoColumn: false, checkboxColumn: false, inlineFilters: false});
    },
    async onload(report) {
        report.page.set_title("حركة الخزينة");
        report.page.add_inner_button(__("Download Workbook Layout"), () => {
            const filters = encodeURIComponent(JSON.stringify(report.get_filter_values()));
            window.open(`/api/method/heavy_equipment_rental.heavy_equipment_rental.report.treasury_workbook.treasury_workbook.download_workbook?filters=${filters}`);
        });
        const style = document.createElement("style");
        style.textContent = ".her-treasury-report .dt-header .dt-cell--header,.her-treasury-report .dt-header .dt-cell--header .dt-cell__content,.her-treasury-report .dt-cell--col-3{background:#f4b183!important;color:#111!important}.her-treasury-report .datatable{direction:rtl;font-family:Calibri,Arial,sans-serif}.her-treasury-report .dt-cell__content{text-align:center;font-weight:700}";
        report.page.wrapper.addClass("her-treasury-report");
        report.page.wrapper.append(style);
        // Explicit route filters take precedence over the workbook convenience defaults.
        const routeFilters = new URLSearchParams(window.location.search);
        if (!report.get_filter_value("account") && !routeFilters.has("company")) {
            const r = await frappe.call({method: "heavy_equipment_rental.heavy_equipment_rental.report.treasury_workbook.treasury_workbook.get_defaults"});
            if (r.message?.company) {
                await her_apply_treasury_filters(report, r.message);
            }
        }
    },
    formatter(value, row, column, data, default_formatter) {
        const formatted = default_formatter(value, row, column, data);
        if (column.fieldname === "description" && data?.voucher && data?.voucher_type) {
            const route = `/app/${frappe.router.slug(data.voucher_type)}/${encodeURIComponent(data.voucher)}`;
            return `<a href="${route}">${frappe.utils.escape_html(value || data.voucher)}</a>`;
        }
        return formatted;
    },
};
