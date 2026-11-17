frappe.query_reports['Crane Expense Report'] = {
    tree: true,
    initial_depth: 1,
    filters: [
        {fieldname: 'company', label: __('Company'), fieldtype: 'Link', options: 'Company',
            default: frappe.defaults.get_user_default('Company'), reqd: 1,
            on_change: async report => {
                await report.set_filter_value({timesheet: '', assignment: '', expense_type: '', employee: ''});
                report.refresh();
            }},
        {fieldname: 'from_date', label: __('From Date'), fieldtype: 'Date', default: frappe.datetime.month_start(), reqd: 1},
        {fieldname: 'to_date', label: __('To Date'), fieldtype: 'Date', default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: 'crane', label: __('Crane'), fieldtype: 'Link', options: 'Crane',
            on_change: async report => { await report.set_filter_value('timesheet', ''); report.refresh(); }},
        {fieldname: 'timesheet', label: __('Crane Timesheet'), fieldtype: 'Link', options: 'Crane Timesheet',
            get_query: () => ({filters: {
                ...(frappe.query_report.get_filter_value('crane') ? {crane: frappe.query_report.get_filter_value('crane')} : {}),
                ...(frappe.query_report.get_filter_value('assignment') ? {assignment: frappe.query_report.get_filter_value('assignment')} : {}),
            }})},
        {fieldname: 'group_by', label: __('Group By'), fieldtype: 'Select',
            options: ['None', 'Crane', 'Timesheet', 'Expense Type', 'Mode of Payment', 'Month'], default: 'Crane'},
        {fieldname: 'show_details', label: __('Show Individual Expenses'), fieldtype: 'Check', default: 1},
        {fieldname: 'chart_by', label: __('Chart By'), fieldtype: 'Select', options: ['Crane', 'Expense Type', 'Month'], default: 'Crane',
            on_change: report => { report.$chart.attr('data-her-chart-title', __('Expenses by {0}', [__(report.get_filter_value('chart_by'))])); report.refresh(); }},
        {fieldname: 'expense_type', label: __('Expense Entry Type'), fieldtype: 'Link', options: 'Expense Entry Type',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company')}})},
        {fieldname: 'mode_of_payment', label: __('Mode of Payment'), fieldtype: 'Link', options: 'Mode of Payment'},
        {fieldname: 'source', label: __('Expense Source'), fieldtype: 'Select', options: ['All', 'Grouped Expense', 'Expense Entry'], default: 'All'},
        {fieldname: 'assignment', label: __('Rental Contract'), fieldtype: 'Link', options: 'Rental Contract',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company')}})},
        {fieldname: 'employee', label: __('Driver'), fieldtype: 'Link', options: 'Employee',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company')}})},
    ],
    onload(report) {
        report.page.main.attr('data-her-expenses', '1');
        report.page.main.find('.her-expense-intro').remove();
        const advancedNames = ['expense_type', 'mode_of_payment', 'source', 'assignment', 'employee'];
        const advanced = report.filters.filter(f => advancedNames.includes(f.df.fieldname));
        for (const field of report.filters) {
            const wrapper = $(field.wrapper);
            wrapper.find('.her-expense-filter-label').remove();
            if (field.df.fieldtype !== 'Check') {
                const id = 'her-expense-filter-' + field.df.fieldname;
                field.$input.attr('id', id);
                $('<label class="her-expense-filter-label">').attr('for', id).text(__(field.df.label)).prependTo(wrapper);
            }
        }
        report.page.page_form.find('.her-expense-filter-toggle').remove();
        let expanded = advanced.some(f => f.get_value() && !(f.df.fieldname === 'source' && f.get_value() === 'All'));
        const toggle = $('<button type="button" class="btn btn-default btn-sm her-expense-filter-toggle">').appendTo(report.page.page_form);
        const apply = () => {
            advanced.forEach(f => $(f.wrapper).toggle(expanded));
            toggle.text(expanded ? __('Fewer Filters') : __('More Filters')).attr('aria-expanded', String(expanded));
        };
        toggle.on('click', () => { expanded = !expanded; apply(); });
        apply();
        report.$chart.attr('data-her-chart-title', __('Expenses by {0}', [__(report.get_filter_value('chart_by'))]));
        const esc = frappe.utils.escape_html;
        report.page.main.prepend(`<div class="her-expense-intro">
            <div><span class="her-expense-eyebrow">${esc(__('EXPENSE OVERVIEW'))}</span>
            <h3>${esc(__('Every expense. A clearer picture.'))}</h3>
            <p>${esc(__('Compare cranes, explore totals, and open the original accounting documents.'))}</p></div>
            <span class="her-expense-status">${esc(__('Posted expenses only'))}</span>
        </div>`);
        if (!document.getElementById('her-expense-report-style')) {
            $('<style id="her-expense-report-style">').text(`
                [data-her-expenses="1"] .her-expense-intro {display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px 28px;margin:16px 0 20px;border-radius:16px;background:linear-gradient(120deg,#142e48,#20506a);color:#fff;border-inline-start:5px solid #e7ba5a;}
                [data-her-expenses="1"] .her-expense-eyebrow {font-size:11px;letter-spacing:1.4px;font-weight:700;color:#edce8f;}
                [data-her-expenses="1"] .her-expense-intro h3 {font-size:23px;line-height:1.4;color:#fff;margin:6px 0;}
                [data-her-expenses="1"] .her-expense-intro p {color:#d9e6ed;margin:0;font-size:13px;}
                [data-her-expenses="1"] .her-expense-status {white-space:nowrap;border:1px solid #72949f;padding:7px 12px;border-radius:20px;font-size:12px;color:#e1f4e9;}
                [data-her-expenses="1"] .report-summary {border:0;background:transparent;gap:12px;padding:0;margin:0 0 20px;}
                [data-her-expenses="1"] .summary-item {background:var(--card-bg);border:1px solid var(--border-color);border-radius:12px;padding:18px;min-width:180px;max-width:none;min-height:112px;height:auto;margin:0;flex:1;box-shadow:0 3px 10px #10263d06;}
                [data-her-expenses="1"] .summary-label {white-space:normal;line-height:1.4;overflow:visible!important;}
                [data-her-expenses="1"] .summary-value {line-height:1.5;padding-top:8px;overflow:visible!important;}
                [data-her-expenses="1"] .her-expense-filter-label {display:block;font-size:11px;font-weight:600;color:var(--text-muted);margin-bottom:5px;}
                [data-her-expenses="1"] .her-expense-filter-toggle {align-self:center;margin:10px;}
                [data-her-expenses="1"] .chart-wrapper::before {content:attr(data-her-chart-title);display:block;font-size:14px;font-weight:650;padding:16px 20px 0;color:var(--text-color);}
                [data-her-expenses="1"] .chart-wrapper {border:1px solid var(--border-color);border-radius:14px;background:var(--card-bg);margin-bottom:20px;}
                [data-her-expenses="1"] .report-wrapper {border-radius:12px;overflow:hidden;border:1px solid var(--border-color);}
                [data-her-expenses="1"] .her-expense-group {font-weight:700;color:var(--text-color);}
                [data-her-expenses="1"] .her-expense-amount {font-weight:650;font-variant-numeric:tabular-nums;color:var(--blue-600,#3979bc);}
                @media(max-width:600px) {[data-her-expenses="1"] .her-expense-intro {padding:18px;align-items:flex-start;flex-direction:column;gap:12px;} [data-her-expenses="1"] .her-expense-intro h3 {font-size:20px;} [data-her-expenses="1"] .summary-item {min-width:130px;} [data-her-expenses="1"] .page-form .frappe-control {width:50%;} [data-her-expenses="1"] .summary-value {font-size:17px;}}
                @media print {.her-expense-intro {display:none!important;}}
            `).appendTo(document.head);
        }
        if (!report.her_expense_cleanup) {
            report.her_expense_cleanup = true;
            frappe.router.on('change', () => {
                if (frappe.get_route()[1] !== 'Crane Expense Report') {
                    report.page.main.removeAttr('data-her-expenses').find('.her-expense-intro, .her-expense-filter-label, .her-expense-filter-toggle').remove();
                }
            });
        }
    },
    formatter(value, row, column, data, default_formatter) {
        const formatted = column.fieldname === 'label' ? frappe.utils.escape_html(value || '')
            : default_formatter(value, row, column, data);
        if (data?.is_group) return `<span class="her-expense-group">${formatted}</span>`;
        if (column.fieldname === 'amount') return `<span class="her-expense-amount">${formatted}</span>`;
        return formatted;
    },
};
