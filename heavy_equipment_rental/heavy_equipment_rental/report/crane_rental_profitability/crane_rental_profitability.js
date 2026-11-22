const profitMetrics = {income: "Income", expenses: "Expenses", net_sales: "Net Profit"};

async function showProfitDetails(report, metric, source) {
    const current = report.get_filter_values();
    const filters = {...current, view: "Document Details"};
    let rows;
    if (source?.voucher) {
        rows = [source];
    } else {
        if (source?.crane) filters.crane = source.crane;
        if (source?.assignment) filters.assignment = source.assignment;
        if (source?.month) {
            const month = moment(source.month, "YYYY-MM");
            filters.from_date = [filters.from_date, month.startOf("month").format("YYYY-MM-DD")].sort()[1];
            filters.to_date = [filters.to_date, month.endOf("month").format("YYYY-MM-DD")].sort()[0];
        }
        const result = await frappe.xcall("frappe.desk.query_report.run", {
            report_name: "Crane Rental Profitability", filters, ignore_prepared_report: true,
        });
        rows = result.result.filter(row => row.voucher);
        if (source && current.view === "By Contract" && !source.assignment) {
            rows = rows.filter(row => !row.assignment);
        }
    }

    const net = metric === "net_sales";
    rows = rows.filter(row => net ? row.income || row.expenses : row[metric]);
    const currency = source?.currency || report.raw_data.report_summary[0].currency;
    const scope = source?.voucher || source?.crane_name || source?.assignment || source?.month ||
        (source ? __("Unassigned") : __("Total"));
    const dialog = new frappe.ui.Dialog({
        title: frappe.utils.escape_html(__(profitMetrics[metric]) + " · " + scope),
        size: "large", fields: [{fieldtype: "HTML", fieldname: "breakdown"}],
    });
    const content = $(dialog.fields_dict.breakdown.wrapper);
    const amounts = net ? ["income", "expenses", "net_sales"] : [metric];
    if (rows.length) {
        const table = $('<table class="table table-sm table-hover">').appendTo(
            $('<div class="table-responsive">').appendTo(content));
        const header = $("<tr>").appendTo($("<thead>").appendTo(table));
        for (const label of ["Posting Date", "Document", "Description", ...amounts.map(key => profitMetrics[key])]) {
            $('<th scope="col">').text(__(label)).appendTo(header);
        }
        const body = $("<tbody>").appendTo(table);
        for (const entry of rows) {
            const line = $("<tr>").appendTo(body);
            $("<td>").text(frappe.datetime.str_to_user(entry.posting_date)).appendTo(line);
            const link = $("<td>").appendTo(line);
            $("<a>").attr("href", frappe.utils.get_form_link(entry.voucher_type, entry.voucher))
                .text(entry.voucher).appendTo(link);
            $("<td>").text(strip_html(entry.description || "")).appendTo(line);
            for (const key of amounts) $("<td>").text(format_currency(entry[key], currency)).appendTo(line);
        }
        const total = $("<tr>").addClass("font-weight-bold").appendTo($("<tfoot>").appendTo(table));
        $('<th colspan="3" scope="row">').text(__("Total")).appendTo(total);
        for (const key of amounts) {
            const value = rows.reduce((sum, entry) => sum + entry[key], 0);
            $("<td>").text(format_currency(value, currency)).appendTo(total);
        }
    } else {
        $("<p>").addClass("text-muted").text(__("No transactions in this period.")).appendTo(content);
    }
    dialog.show();
}

frappe.query_reports["Crane Rental Profitability"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
            default: frappe.defaults.get_user_default("Company"), reqd: 1},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            default: frappe.datetime.month_start(), reqd: 1},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: "view", label: __("View"), fieldtype: "Select",
            options: ["By Crane", "By Contract", "By Month", "Document Details"], default: "By Crane"},
        {fieldname: "assignment", label: __("Rental Contract"), fieldtype: "Link", options: "Rental Contract",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane"},
    ],
    onload(report) {
        report.page.main.off("click.herProfitDetails").on("click.herProfitDetails", "[data-profit-metric]", async event => {
            event.stopPropagation();
            const button = event.currentTarget;
            const {profitMetric, profitRow} = button.dataset;
            const source = profitRow === undefined ? null : report.datatable.datamanager.getData(Number(profitRow));
            button.disabled = true;
            try {
                await showProfitDetails(report, profitMetric, source);
            } finally {
                button.disabled = false;
            }
        });
        return frappe.after_ajax();
    },
    after_datatable_render() {
        const report = frappe.query_report;
        report.$summary.find(".summary-value").each((index, node) => {
            const field = Object.keys(profitMetrics)[index];
            if (field === "expenses") node.style.setProperty("color", "#df626b", "important");
            if (field && !node.querySelector("button")) {
                $(node).wrapInner($('<button type="button" class="btn btn-link p-0">')
                    .css({color: "inherit", font: "inherit"}).attr("data-profit-metric", field));
            }
        });
    },
    formatter(value, row, column, data, default_formatter) {
        const field = column.fieldname;
        if (field === "crane_name" && data?.crane) {
            return frappe.utils.get_form_link("Crane", data.crane, true, frappe.utils.escape_html(data.crane_name));
        }
        if (field === "assignment" && data && !data.assignment &&
                frappe.query_report.get_filter_value("view") === "By Contract") return __("Unassigned");
        const formatted = default_formatter(value, row, column, data);
        if (!profitMetrics[field] || !data || !row?.meta) return formatted;
        const color = field === "expenses" ? "" : field === "income" ? "text-primary" :
            value < 0 ? "text-danger" : "text-success";
        return `<button type="button" class="btn btn-link btn-xs p-0 ${color}" style="text-decoration:underline;${field === "expenses" ? "color:#df626b" : ""}"
            data-profit-metric="${field}" data-profit-row="${row.meta.rowIndex}">${formatted}</button>`;
    },
};
