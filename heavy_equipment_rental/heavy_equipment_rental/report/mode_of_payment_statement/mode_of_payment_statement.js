frappe.query_reports['Mode of Payment Statement'] = {
    filters: [
        {
            fieldname: 'company', label: __('Company'), fieldtype: 'Link', options: 'Company',
            default: frappe.defaults.get_user_default('Company'), reqd: 1,
        },
        {
            fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date',
            default: frappe.datetime.month_start(), reqd: 1,
        },
        {
            fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date',
            default: frappe.datetime.get_today(), reqd: 1,
        },
        {
            fieldname: 'mode_of_payment', label: __('Mode of Payment'),
            fieldtype: 'Link', options: 'Mode of Payment',
        },
    ],
    onload(report) {
        for (const field of report.filters) {
            const wrapper = $(field.wrapper);
            wrapper.find('.her-payment-filter-label').remove();
            const id = 'her-payment-filter-' + field.df.fieldname;
            field.$input.attr('id', id);
            $('<label class="her-payment-filter-label">')
                .attr('for', id).text(__(field.df.label))
                .css({display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px'})
                .prependTo(wrapper);
        }
    },
    formatter(value, row, column, data, default_formatter) {
        const formatted = ['remarks', 'payment_modes'].includes(column.fieldname)
            ? frappe.utils.escape_html(value || '')
            : default_formatter(value, row, column, data);
        return data?.is_opening ? `<strong>${formatted}</strong>` : formatted;
    },
};
