frappe.query_reports["Monthly Salary Report"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            reqd: 1,
        },
        {
            fieldname: "month",
            label: __("Salary Month"),
            fieldtype: "Date",
            default: frappe.datetime.month_start(),
            reqd: 1,
        },
    ],
    formatter(value, row, column, data, default_formatter) {
        if (column.fieldname === "employee_name") {
            return frappe.utils.escape_html(value || "");
        }
        return default_formatter(value, row, column, data);
    },
};
