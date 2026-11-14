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
        {fieldname: "assignment", label: __("Assignment"), fieldtype: "Link", options: "Crane Assignment",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "timesheet", label: __("Timesheet"), fieldtype: "Link", options: "Crane Timesheet"},
        {fieldname: "sales_invoice", label: __("Sales Invoice"), fieldtype: "Link", options: "Sales Invoice",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"},
    ],
    onload(report) {
        report.page.add_inner_button(__("Crane Distribution Dashboard"), () => {
            frappe.set_route("crane-distribution-dashboard");
        });
        // Link filter validation can finish after route filters are assigned.
        // Wait before the initial query so bookmarked filters reach the server.
        return frappe.after_ajax();
    },
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data?.is_total_row) {
            if (!Object.prototype.hasOwnProperty.call(data, column.fieldname)) return "";
            return `<strong>${value ?? ""}</strong>`;
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
