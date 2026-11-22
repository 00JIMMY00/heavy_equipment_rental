frappe.query_reports["Fleet Utilization and Availability"] = {
    filters: [
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -29), reqd: 1},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane"},
    ],
    async onload(report) {
        await frappe.require("/assets/heavy_equipment_rental/js/dispatch_report.js");
        heavy_equipment_rental.dispatch_report.bind(report);
    },
    formatter(...args) {
        return heavy_equipment_rental.dispatch_report.formatter(...args);
    },
};
