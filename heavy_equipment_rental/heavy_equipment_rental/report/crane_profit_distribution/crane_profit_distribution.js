// Settlement totals use the full saved distribution, even under a partner filter.
const distributionAmounts = {
    revenue: ["Source Details", "revenue"], expenses: ["Source Details", "expenses"],
    operating_fee: ["Distribution Details", "operating_share"],
    company_operating: ["Distribution Details", "operating_share", "Our Company"],
    company_residual: ["Distribution Details", "residual_share", "Our Company"],
    company_total: ["Distribution Details", "total_share", "Our Company"],
    external_total: ["Distribution Details", "total_share", "External Partners"],
    posted_entitlement: ["Distribution Details", "posted_entitlement"],
    pending_entitlement: ["Distribution Details", "pending_entitlement"],
    cash_paid: ["Distribution Details", "cash_paid"], adjustments: ["Distribution Details", "adjustments"],
    outstanding: ["Distribution Details", "outstanding_amount"],
    selected_paid: ["Distribution Details", "paid_adjusted"],
    selected_entitlement: ["Distribution Details", "posted_entitlement"],
    selected_outstanding: ["Distribution Details", "outstanding_amount"],
};

async function showDistributionAmount(report, source, field, label) {
    const filters = report.get_filter_values();
    const summary = !source || filters.view === "Settlement Summary";
    let selected;
    if (!source) {
        const scope = await frappe.xcall("frappe.desk.query_report.run", {
            report_name: report.report_name, filters: {...filters, view: "Settlement Summary"}, ignore_prepared_report: true,
        });
        selected = new Set(scope.result.filter(entry => entry.settlement_status ===
            __(field === "pending_entitlement" ? "Draft" : "Submitted")).map(entry => entry.settlement));
    }
    const [view, amount, participant] = summary ? distributionAmounts[field] : ["Distribution Details", field];
    Object.assign(filters, {view, participant: participant || "All"});
    if (source?.settlement) filters.settlement = source.settlement;
    if (summary && !field.startsWith("selected_")) {
        delete filters.payment_status;
        delete filters.shareholder;
    }
    const result = await frappe.xcall("frappe.desk.query_report.run", {
        report_name: report.report_name, filters, ignore_prepared_report: true,
    });
    if (amount === "paid_adjusted") {
        for (const entry of result.result) entry.paid_adjusted = (entry.cash_paid || 0) + (entry.adjustments || 0);
    }
    const currency = source?.currency || report.raw_data.report_summary[0].currency;
    const rows = result.result.filter(entry => !entry.is_total_row && entry[amount] &&
        (selected ? selected.has(entry.settlement) : entry.settlement_status === source.settlement_status) && (summary ||
        (entry.shareholder === source.shareholder && entry.partner_name === source.partner_name)));
    const dialog = new frappe.ui.Dialog({
        title: frappe.utils.escape_html(label + " · " + (source?.settlement || source?.partner_name || __("Total"))),
        size: "large", fields: [{fieldtype: "HTML", fieldname: "details"}],
    });
    const content = $(dialog.fields_dict.details.wrapper);
    if (rows.length) {
        const table = $('<table class="table table-sm table-hover">').appendTo(
            $('<div class="table-responsive">').appendTo(content));
        const head = $("<tr>").appendTo($("<thead>").appendTo(table));
        for (const title of ["Posting Date", "Document", view === "Source Details" ? "Description" : "Participant Name", label]) {
            $("<th>").text(__(title)).appendTo(head);
        }
        const body = $("<tbody>").appendTo(table);
        for (const entry of rows) {
            const line = $("<tr>").appendTo(body);
            $("<td>").text(frappe.datetime.str_to_user(entry.source_posting_date || entry.posting_date)).appendTo(line);
            const name = entry.source_name || entry.settlement;
            $("<a>").attr("href", frappe.utils.get_form_link(entry.source_doctype || "Crane Profit Settlement", name))
                .text(name).appendTo($("<td>").appendTo(line));
            $("<td>").text(entry.description || entry.expense_type || entry.partner_name || "").appendTo(line);
            $("<td>").text(format_currency(entry[amount], currency)).appendTo(line);
        }
        const foot = $("<tr>").appendTo($("<tfoot>").appendTo(table));
        $('<th colspan="3">').text(__("Total")).appendTo(foot);
        $("<th>").text(format_currency(rows.reduce((sum, r) => sum + r[amount], 0), currency)).appendTo(foot);
    } else {
        $("<p>").text(__("No transactions in this period.")).appendTo(content);
    }
    dialog.show();
}

frappe.query_reports["Crane Profit Distribution"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
            default: frappe.defaults.get_user_default("Company")},
        {fieldname: "view", label: __("View"), fieldtype: "Select", reqd: 1,
            options: ["Settlement Summary", "Participant Summary", "Distribution Details", "Source Details", "Entitlement Movements"], default: "Settlement Summary"},
        {fieldname: "report_date", label: __("Balance As Of"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today()},
        {fieldname: "date_basis", label: __("Date Basis"), fieldtype: "Select",
            options: ["Work Period", "Settlement Posting Date"], default: "Work Period"},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start()},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today()},
        {fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane"},
        {fieldname: "shareholder", label: __("Shareholder"), fieldtype: "Link", options: "Shareholder",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "settlement_status", label: __("Settlement Status"), fieldtype: "Select",
            options: ["Submitted", "Draft", "All"], default: "Submitted"},
        {fieldname: "payment_status", label: __("Entitlement Status"), fieldtype: "Select",
            options: ["", "Unpaid", "Partly Paid", "Paid", "No Entitlement", "Draft", "Awaiting Invoice"]},
        {fieldname: "participant", label: __("Participant"), fieldtype: "Select",
            options: ["All", "Our Company", "External Partners"], default: "All",
            depends_on: "eval:['Participant Summary', 'Distribution Details', 'Entitlement Movements'].includes(doc.view)"},
        {fieldname: "settlement", label: __("Settlement"), fieldtype: "Link", options: "Crane Profit Settlement",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company"), docstatus: ["!=", 2]}})},
        {fieldname: "assignment", label: __("Rental Contract"), fieldtype: "Link", options: "Rental Contract",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "timesheet", label: __("Timesheet"), fieldtype: "Link", options: "Crane Timesheet"},
        {fieldname: "sales_invoice", label: __("Sales Invoice"), fieldtype: "Link", options: "Sales Invoice",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"},
    ],
    onload(report) {
        report.page.main.off("click.herDistribution").on("click.herDistribution", "[data-distribution-field]", async event => {
            const button = event.currentTarget;
            const source = button.dataset.row === undefined ? null : report.datatable.datamanager.getData(Number(button.dataset.row));
            button.disabled = true;
            try {
                await showDistributionAmount(report, source, button.dataset.distributionField, button.dataset.label);
            } finally {
                button.disabled = false;
            }
        });
        const extra = ["date_basis", "settlement_status", "payment_status", "participant",
            "settlement", "assignment", "timesheet", "sales_invoice", "customer"];
        const fields = extra.map(name => report.get_filter(name));
        const details = $("<details>").css({flexBasis: "100%", padding: "0.4rem 0.75rem"})
            .appendTo(report.page.page_form);
        $("<summary>").text(__("More Filters")).css({cursor: "pointer", fontWeight: 600}).appendTo(details);
        const panel = $("<div>").css({display: "flex", flexWrap: "wrap", gap: "0.5rem", paddingTop: "0.6rem"})
            .appendTo(details);
        for (const filter of fields) panel.append(filter.wrapper);
        details.prop("open", fields.some(f => (f.get_value() || "") !== (f.df.default || "")));
        report.page.add_inner_button(__("Crane Distribution Dashboard"), () => {
            frappe.set_route("crane-distribution-dashboard");
        });
        // Link filter validation can finish after route filters are assigned.
        // Wait before the initial query so bookmarked filters reach the server.
        return frappe.after_ajax();
    },
    after_datatable_render() {
        const metrics = ["revenue", "expenses", "company_operating", "company_residual", "company_total",
            "posted_entitlement", "cash_paid", "adjustments", "outstanding", "pending_entitlement",
            "selected_entitlement", "selected_paid", "selected_outstanding"];
        frappe.query_report.$summary.find(".summary-value").each((index, node) => {
            if (node.querySelector("button") || !metrics[index]) return;
            $(node).wrapInner($('<button type="button" class="btn btn-link p-0">')
                .css({color: "inherit", font: "inherit"}).attr({
                    "data-distribution-field": metrics[index], "data-label": $(node).siblings(".summary-label").text(),
                }));
        });
    },
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (["expenses", "expense_burden"].includes(column.fieldname)) {
            value = `<span class="her-distribution-cost">${value ?? ""}</span>`;
        }
        if (data?.is_total_row) {
            if (!Object.prototype.hasOwnProperty.call(data, column.fieldname)) return "";
            return `<strong>${value ?? ""}</strong>`;
        }
        if (column.fieldname === "crane_name" && data?.crane) {
            return frappe.utils.get_form_link("Crane", data.crane, true,
                frappe.utils.escape_html(data.crane_name || data.crane));
        }
        if (column.fieldtype === "Currency" && data && row?.meta) {
            const view = frappe.query_report.get_filter_value("view");
            const field = column.fieldname;
            if ((view === "Settlement Summary" && distributionAmounts[field]) || view === "Participant Summary") {
                return `<button type="button" class="btn btn-link btn-xs p-0" style="text-decoration:underline"
                    data-distribution-field="${field}" data-row="${row.meta.rowIndex}"
                    data-label="${frappe.utils.escape_html(column.label)}">${value}</button>`;
            }
            const name = data.source_name || data.voucher_no || data.settlement;
            if (name) return frappe.utils.get_form_link(data.source_doctype || data.voucher_type ||
                "Crane Profit Settlement", name, true, value);
        }
        if (column.fieldname === "status" && data) {
            const color = {Paid: "green", "Partly Paid": "orange", Unpaid: "red", Draft: "gray",
                "Awaiting Invoice": "gray", "Retained by Company": "blue"}[data.status] || "gray";
            return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.status || ""))}</span>`;
        }
        if (column.fieldname === "participant" && data) return frappe.utils.escape_html(__(data.participant || ""));
        return value;
    },
};
