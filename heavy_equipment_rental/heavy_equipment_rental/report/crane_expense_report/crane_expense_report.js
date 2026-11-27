frappe.query_reports['Crane Expense Report'] = {
    tree: true,
    initial_depth: 1,
    filters: [
        {fieldname: 'company', label: __('Company'), fieldtype: 'Link', options: 'Company',
            default: frappe.defaults.get_user_default('Company'), reqd: 1,
            on_change: async report => {
                await report.set_filter_value({
                    timesheet: '', assignment: '', expense_type: '', employee: '', cost_center: '', grouped_expense: '',
                });
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
        {fieldname: 'chart_by', label: __('Chart By'), fieldtype: 'Select', options: ['Crane', 'Expense Type', 'Month'], default: 'Crane',
            on_change: report => { report.$chart.attr('data-her-chart-title', __('Expenses by {0}', [__(report.get_filter_value('chart_by'))])); report.refresh(); }},
        {fieldname: 'expense_type', label: __('Expense Entry Type'), fieldtype: 'Link', options: 'Expense Entry Type',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company')}})},
        {fieldname: 'grouped_expense', label: __('Grouped Expense'), fieldtype: 'Link', options: 'Grouped Expense',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company'), docstatus: 1}})},
        {fieldname: 'mode_of_payment', label: __('Mode of Payment'), fieldtype: 'Link', options: 'Mode of Payment'},
        {fieldname: 'cost_center', label: __('Cost Center'), fieldtype: 'Link', options: 'Cost Center',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company'), is_group: 0}})},
        {fieldname: 'assignment', label: __('Rental Contract'), fieldtype: 'Link', options: 'Rental Contract',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company')}})},
        {fieldname: 'employee', label: __('Employee'), fieldtype: 'Link', options: 'Employee',
            get_query: () => ({filters: {company: frappe.query_report.get_filter_value('company')}})},
        {fieldname: 'show_details', label: __('Show Individual Expenses'), fieldtype: 'Check', default: 1},
    ],
    onload(report) {
        report.page.main.attr('data-her-expenses', '1');
        const advancedNames = ['expense_type', 'grouped_expense', 'mode_of_payment', 'cost_center', 'employee', 'assignment'];
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
        const form = report.page.page_form;
        const chart = report.get_filter('chart_by');
        const details = report.get_filter('show_details');
        const primary = report.filters.filter(f => f !== chart && f !== details && !advanced.includes(f));
        $('<div class="her-expense-filter-grid">').appendTo(form).append(primary.map(f => f.wrapper));
        const options = $('<div class="her-expense-filter-grid her-expense-view-options">').appendTo(form);
        options.append(chart.wrapper);
        const actions = $('<div class="her-expense-filter-actions">').appendTo(options);
        const panel = $('<div id="her-expense-advanced-filters" class="her-expense-filter-grid her-expense-advanced">')
            .appendTo(form).append(advanced.map(f => f.wrapper));
        const toggle = $('<button type="button" class="btn btn-default btn-sm her-expense-filter-toggle">')
            .attr('aria-controls', panel.attr('id')).appendTo(actions);
        actions.append(details.wrapper);
        let expanded = advanced.some(f => f.get_value());
        const apply = () => {
            panel.prop('hidden', !expanded);
            toggle.text(expanded ? __('Fewer Filters') : __('More Filters')).attr('aria-expanded', String(expanded));
        };
        toggle.on('click', () => { expanded = !expanded; apply(); });
        apply();
        report.$chart.attr('data-her-chart-title', __('Expenses by {0}', [__(report.get_filter_value('chart_by'))]));
        if (!document.getElementById('her-expense-report-style')) {
            $('<style id="her-expense-report-style">').text(`
                [data-her-expenses="1"] .report-summary {border:0;border-bottom:1px solid var(--border-color);border-radius:0;background:transparent;justify-content:flex-start;padding:12px;margin:0 0 12px;}
                [data-her-expenses="1"] .summary-item {flex-direction:row;align-items:baseline;justify-content:flex-start;gap:12px;max-width:none;min-width:0;height:auto;margin:0;}
                [data-her-expenses="1"] .summary-label, [data-her-expenses="1"] .summary-value {padding:0;line-height:1.5;white-space:normal;overflow:visible!important;text-align:start;}
                [data-her-expenses="1"] .her-expense-filter-label {display:block;font-size:11px;font-weight:600;color:var(--text-muted);margin-bottom:5px;}
                [data-her-expenses="1"] .page-form {
                    --her-expense-columns: 6;
                    --her-expense-control-height: 28px;
                    flex-direction: column;
                    flex-wrap: nowrap;
                    gap: 12px;
                    padding: 14px 12px;
                }
                [data-her-expenses="1"] .her-expense-filter-grid {
                    display: grid;
                    grid-template-columns: repeat(var(--her-expense-columns), minmax(0, 1fr));
                    align-items: end;
                    gap: 12px;
                }
                #page-query-report [data-her-expenses="1"] .her-expense-filter-grid .form-group {
                    max-width: none;
                    min-width: 0;
                    padding: 0;
                    margin: 0;
                }
                [data-her-expenses="1"] .her-expense-filter-grid select,
                [data-her-expenses="1"] .her-expense-filter-toggle {height: var(--her-expense-control-height);}
                #page-query-report [data-her-expenses="1"] .her-expense-filter-grid .select-icon.xs {
                    top: auto;
                    bottom: 0;
                    height: var(--her-expense-control-height);
                    display: grid;
                    place-items: center;
                }
                [data-her-expenses="1"] .her-expense-filter-actions {
                    grid-column: 2 / -1;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                [data-her-expenses="1"] .her-expense-filter-toggle {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    min-inline-size: 8em;
                    white-space: nowrap;
                }
                [data-her-expenses="1"] .her-expense-filter-actions .form-group {flex: 0 1 auto;}
                [data-her-expenses="1"] .her-expense-filter-actions .checkbox {margin: 0;}
                [data-her-expenses="1"] .her-expense-filter-actions .checkbox label {display: flex;}
                [data-her-expenses="1"] .her-expense-advanced {border-top: 1px solid var(--border-color); padding-top: 12px;}
                [data-her-expenses="1"] .her-expense-advanced[hidden] {display: none;}
                [data-her-expenses="1"] .chart-wrapper::before {content:attr(data-her-chart-title);display:block;font-size:14px;font-weight:650;padding:16px 20px 0;color:var(--text-color);}
                [data-her-expenses="1"] .chart-wrapper {border:1px solid var(--border-color);border-radius:14px;background:var(--card-bg);margin-bottom:20px;}
                [data-her-expenses="1"] .report-wrapper {border-radius:12px;overflow:hidden;border:1px solid var(--border-color);}
                [data-her-expenses="1"] .dt-scrollable .dt-row:is(:hover, :focus-within) > .dt-cell {
                    --dt-cell-bg: color-mix(in srgb, var(--fg-color) 87%, var(--blue-500));
                }
                [data-her-expenses="1"] .her-expense-group {font-weight:700;color:var(--text-color);}
                [data-her-expenses="1"] {--her-expense-red:#d00000;}
                html[data-theme="dark"] [data-her-expenses="1"] {--her-expense-red:#ff6868;}
                [data-her-expenses="1"] .her-expense-amount {font-weight:650;font-variant-numeric:tabular-nums;color:var(--her-expense-red);}
                [data-her-expenses="1"] .summary-value {color:var(--text-color);font-variant-numeric:tabular-nums;}
                [data-her-expenses="1"] .her-expense-crane {text-decoration:underline;text-underline-offset:2px;}
                @media (max-width: 1100px) {
                    [data-her-expenses="1"] .page-form {--her-expense-columns: 3;}
                }
                @media (max-width: 600px) {
                    [data-her-expenses="1"] .page-form {--her-expense-columns: 2;}
                    [data-her-expenses="1"] .her-expense-filter-actions {display: contents;}
                    [data-her-expenses="1"] .her-expense-filter-toggle {justify-self: start;}
                    [data-her-expenses="1"] .her-expense-filter-actions .form-group {grid-column: 1 / -1;}
                }
            `).appendTo(document.head);
        }
        if (!report.her_expense_cleanup) {
            report.her_expense_cleanup = true;
            frappe.router.on('change', () => {
                if (frappe.get_route()[1] !== 'Crane Expense Report') {
                    report.page.main.removeAttr('data-her-expenses').find('.her-expense-filter-label, .her-expense-filter-toggle').remove();
                }
            });
        }
    },
    formatter(value, row, column, data, default_formatter) {
        if (column.fieldname === 'crane_name' && data?.crane) {
            const label = frappe.utils.escape_html(value || '');
            const url = frappe.utils.get_form_link('Crane', data.crane);
            return `<a class="her-expense-crane ${data.is_group ? 'her-expense-group' : ''}" href="${url}">${label}</a>`;
        }
        const formatted = ['description', 'crane_name'].includes(column.fieldname) ? frappe.utils.escape_html(value || '')
            : default_formatter(value, row, column, data);
        if (data?.is_group || data?.is_total_row) return `<span class="her-expense-group">${formatted}</span>`;
        if (column.fieldname === 'description' && data?.maintenance) {
            const url = frappe.utils.get_form_link('Crane Maintenance', data.maintenance);
            return `<a href="${url}">${formatted}</a>`;
        }
        if (column.fieldname === 'amount') {
            if (data?.source_type === 'Stock Entry') {
                const url = frappe.utils.get_form_link('Stock Entry', data.source);
                return `<a class="her-expense-amount" href="${url}">${formatted}</a>`;
            }
            return `<span class="her-expense-amount">${formatted}</span>`;
        }
        return formatted;
    },
};
