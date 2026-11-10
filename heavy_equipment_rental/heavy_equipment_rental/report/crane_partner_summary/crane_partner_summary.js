frappe.query_reports["Crane Partner Summary"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
            on_change() { frappe.query_report.set_filter_value("shareholder", ""); frappe.query_report.refresh(); } },
        { fieldname: "report_date", label: __("Report Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today() },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
        { fieldname: "shareholder", label: __("Shareholder"), fieldtype: "Link", options: "Shareholder",
            get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } }) },
        { fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane" },
        { fieldname: "timesheet", label: __("Timesheet"), fieldtype: "Link", options: "Crane Timesheet" },
        { fieldname: "status", label: __("Entitlement Status"), fieldtype: "Select",
            options: ["", "Awaiting Invoice", "Draft", "Unpaid", "Partly Paid", "Paid", "No Entitlement"] },
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data) {
            const color = { "Paid": "green", "Partly Paid": "orange", "Unpaid": "red", "Draft": "gray", "Awaiting Invoice": "gray" }[data.status] || "gray";
            return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(data.status || ""))}</span>`;
        }
        return value;
    },
};
