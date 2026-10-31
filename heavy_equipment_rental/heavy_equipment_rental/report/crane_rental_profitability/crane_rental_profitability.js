frappe.query_reports["Crane Rental Profitability"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
            default: frappe.defaults.get_user_default("Company"), reqd: 1},
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            default: frappe.datetime.month_start(), reqd: 1},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: "assignment", label: __("Assignment"), fieldtype: "Link", options: "Crane Assignment",
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value("company")}})},
        {fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane"},
    ],
};
