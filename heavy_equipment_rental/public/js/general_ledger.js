(() => {
    const report = frappe.query_reports["General Ledger"];
    if (report.filters.some(f => f.fieldname === "cps")) return;
    const filters = [
        {
            fieldname: "crane", label: __("Crane"), fieldtype: "Link", options: "Crane",
        },
        {
            fieldname: "cps", label: __("Crane Profit Settlement (CPS)"),
            fieldtype: "Link", options: "Crane Profit Settlement",
            get_query: () => {
                const filters = {company: frappe.query_report.get_filter_value("company")};
                const crane = frappe.query_report.get_filter_value("crane");
                if (crane) filters.crane = crane;
                return {filters};
            },
        },
    ];
    report.filters.splice(1, 0, ...filters);
})();
