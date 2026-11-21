frappe.query_reports["Employee Salary Withdrawals"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
            reqd: 1, default: frappe.defaults.get_user_default("Company"),
            on_change(report) { report.set_filter_value("employee", ""); }},
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1,
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1,
            default: frappe.datetime.month_start()},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1,
            default: frappe.datetime.month_end()},
    ],
};
