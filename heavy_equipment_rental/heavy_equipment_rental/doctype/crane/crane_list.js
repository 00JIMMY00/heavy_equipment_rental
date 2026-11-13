frappe.listview_settings["Crane"] = {
    formatters: {
        crane_list_image(value, df, doc) {
            if (!value) return `<span class="text-muted">—</span>`;
            const url = frappe.utils.escape_html(value);
            const title = frappe.utils.escape_html(doc.crane_name || doc.name || "");
            return `<img src="${url}" alt="${title}" style="width: 44px; height: 34px; object-fit: contain; border-radius: 4px;">`;
        },
    },
};
