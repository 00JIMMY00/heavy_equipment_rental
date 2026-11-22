frappe.provide("heavy_equipment_rental.dispatch_report");

heavy_equipment_rental.dispatch_report = {
    tips: {
        utilization: "Worked booked days divided by elapsed booked days.",
        missing_days: "Past booked days without a submitted timesheet entry.",
        downtime_days: "Submitted days with zero work and zero overtime.",
        risk_count: "Visible bookings in the next 30 days while this repair is open.",
        repair_days: "Calendar days from the start of this repair through completion or today.",
        cost: "Recorded Repair Cost",
    },
    formatter(value, row, column, data, format) {
        const field = column.fieldname;
        const esc = frappe.utils.escape_html;
        if (!data) return format(value, row, column, data);
        if (field === "crane_name" && data.crane)
            return frappe.utils.get_form_link("Crane", data.crane, true, esc(value || data.crane));
        if (data.is_total && data[field] == null) return "";
        if (value == null && ["cost", "utilization"].includes(field)) return "—";
        const formatted = format(value, row, column, data);
        if (data.is_total) return '<strong>' + formatted + '</strong>';
        if (!row?.meta || data[field] == null || !["Int", "Currency", "Percent"].includes(column.fieldtype)) return formatted;
        const tip = __(heavy_equipment_rental.dispatch_report.tips[field] || column.label);
        const color = {cost: "#df626b", risk_count: "#df626b", missing_days: "#bc791d",
            worked_days: "#35956b", elapsed_worked: "#35956b", downtime_days: "#787db7"}[field];
        return $('<button type="button" class="btn btn-link p-0">').attr({
            title: tip, "data-dispatch-field": field, "data-dispatch-row": row.meta.rowIndex,
        }).css({color: color || "var(--text-color)", textDecoration: "underline"}).html(formatted)[0].outerHTML;
    },
    bind(report) {
        report.page.main.off("click.herDispatch").on("click.herDispatch", "[data-dispatch-field]", async event => {
            const button = event.currentTarget;
            const field = button.dataset.dispatchField;
            const row = report.datatable.datamanager.getData(Number(button.dataset.dispatchRow));
            const filters = report.get_filter_values();
            const title = report.columns.find(c => c.fieldname === field).label;
            const dialog = new frappe.ui.Dialog({title: frappe.utils.escape_html(title + " · " + row.crane_name),
                size: "large", fields: [{fieldname: "details", fieldtype: "HTML"}]});
            const area = $(dialog.fields_dict.details.wrapper);
            const tip = heavy_equipment_rental.dispatch_report.tips[field];
            if (tip) $("<p>").text(__(tip)).appendTo(area);
            const table = $('<table class="table table-sm table-hover">').appendTo(area);
            const link = (cell, dt, name) => $("<a>").attr("href", frappe.utils.get_form_link(dt, name)).text(name).appendTo(cell);
            let total = row[field];
            if (field === "cost" || field === "risk_count") {
                for (const item of field === "cost" ? row.cost_sources : row.risk_sources) {
                    const line = $("<tr>").appendTo(table);
                    link($("<td>").appendTo(line), item.doctype, item.name);
                    $("<td>").text(field === "cost" ? format_currency(item.amount, row.currency) : frappe.datetime.str_to_user(item.day)).appendTo(line);
                }
                if (field === "cost") total = format_currency(total, row.currency);
            } else if (field === "repair_days") {
                const line = $("<tr>").appendTo(table);
                link($("<td>").appendTo(line), "Crane Maintenance", row.maintenance);
                $("<td>").text([row.started, row.ended || frappe.datetime.get_today()].map(d => frappe.datetime.str_to_user(d)).join(" – ")).appendTo(line);
            } else {
                const days = await frappe.xcall("heavy_equipment_rental.heavy_equipment_rental.report.fleet_utilization_and_availability.fleet_utilization_and_availability.day_details",
                    {crane: row.crane, from_date: filters.from_date, to_date: filters.to_date, metric: field});
                for (const entry of days) {
                    const line = $("<tr>").appendTo(table);
                    $("<td>").text(frappe.datetime.str_to_user(entry.day)).appendTo(line);
                    const cell = $("<td>").appendTo(line);
                    for (const [dt, name] of entry.documents) {
                        link(cell, dt, name);
                        cell.append(" ");
                    }
                    if (field === "utilization") $("<td>").text(entry.worked ? __("Worked") : "—").appendTo(line);
                }
                if (field === "utilization") total = row.elapsed_worked + " / " + row.elapsed_days + " (" + format_number(total, null, 1) + "%)";
            }
            $("<strong>").text(__("Total") + " · " + total).appendTo(area);
            dialog.show();
        });
    },
};
