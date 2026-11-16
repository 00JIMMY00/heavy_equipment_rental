frappe.listview_settings["Crane"] = {
    add_fields: ["hired_from_supplier", "supplier", "ownership_classification"],
    before_render() {
        const listview = frappe.get_list_view("Crane");
        if (!listview) return;
        const names = (listview.data || []).map(row => row.name);
        if (!names.length) return;
        const request = listview._ownership_request = (listview._ownership_request || 0) + 1;
        frappe.call({
            method: "heavy_equipment_rental.crane_ownership.list_ownership",
            args: {cranes: names},
        }).then(({message}) => {
            if (request !== listview._ownership_request) return;
            listview.$result.find("[data-crane-ownership]").each(function () {
                const name = this.dataset.craneOwnership;
                const doc = listview.data.find(row => row.name === name);
                if (doc) this.innerHTML = crane_list_ownership(doc, message?.[name] || []);
            });
        });
    },
    formatters: {
        ownership_classification(value, df, doc) {
            return `<span data-crane-ownership="${frappe.utils.escape_html(doc.name)}" style="display:block;width:100%">${crane_list_ownership(doc, [])}</span>`;
        },
        crane_list_image(value, df, doc) {
            if (!value) return `<span class="text-muted">—</span>`;
            const url = frappe.utils.escape_html(value);
            const title = frappe.utils.escape_html(doc.crane_name || doc.name || "");
            return `<img src="${url}" alt="${title}" style="width: 44px; height: 34px; object-fit: contain; border-radius: 4px;">`;
        },
    },
};


function crane_list_ownership(doc, rows) {
    const esc = frappe.utils.escape_html;
    const rented = !!doc.hired_from_supplier;
    const label = rented ? __("Hired from Supplier") : __(doc.ownership_classification || "Ownership Not Recorded");
    const colors = ["#4169d1", "#138575", "#9a53c6", "#c47715", "#ce5268", "#387eaa", "#7b8738", "#875c48"];
    const total = Math.max(100, rows.reduce((sum, row) => sum + Math.max(0, flt(row.ownership_percentage)), 0));
    const details = rented ? doc.supplier || "" : rows.map(row =>
        `${row.is_company ? __("Our Company") : row.shareholder || __("Partner")}: ${flt(row.ownership_percentage)}%`).join(" · ");
    const segments = rented
        ? '<i style="width:100%;background:#c47715"></i>'
        : rows.map((row, index) => `<i style="width:${Math.max(0, flt(row.ownership_percentage)) / total * 100}%;background:${colors[index % colors.length]}"></i>`).join("");
    return `<span title="${esc([label, details].filter(Boolean).join(" · "))}" style="display:block;line-height:1.3;padding:3px 0"><span style="display:block;font-size:11px;overflow:hidden;text-overflow:ellipsis">${esc(label)}</span><span role="img" aria-label="${esc(details || label)}" style="display:flex;overflow:hidden;height:6px;border-radius:5px;background:var(--control-bg);margin-top:4px">${segments}</span></span>`;
}
