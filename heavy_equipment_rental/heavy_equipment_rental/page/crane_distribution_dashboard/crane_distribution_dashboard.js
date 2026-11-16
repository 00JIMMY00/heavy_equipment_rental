frappe.pages['crane-distribution-dashboard'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: 'لوحة المستحقات والشراكة', single_column: true});
    new CraneDistributionDashboard(page);
};

class CraneDistributionDashboard {
    constructor(page) {
        this.page = page;
        this.controls = {};
        this.request = 0;
        this.pageIndex = 0;
        this.search = '';
        this.ready = false;
        this.root = $(`<div class="cdd" dir="rtl">
            <section class="cdd-hero"><div><span class="cdd-eyebrow">متابعة مالية • توزيع الأرباح</span><h2>المستحقات والشراكة</h2><p>من تفاصيل الاتفاق إلى السداد، صورة واضحة لكل تسوية.</p></div><span class="cdd-count">—</span></section>
            <section class="cdd-panel"><div class="cdd-filter-head"><h3>حدد نطاق المتابعة</h3><button class="btn btn-default btn-sm" data-action="reset">إعادة ضبط الفلاتر</button></div><div class="cdd-filters"></div><details><summary>فلاتر المستندات والأطراف</summary><div class="cdd-advanced cdd-filters"></div></details></section>
            <div class="cdd-feedback" role="status" aria-live="polite"></div>
            <div class="cdd-results"></div>
        </div>`).appendTo(page.main);
        this.addFilters();
        this.root.on('click', '[data-action="reset"]', () => this.reset());
        this.root.on('click', '[data-status]', (event) => this.controls.payment_status.set_value(event.currentTarget.dataset.status));
        this.root.on('input', '.cdd-search', (event) => { this.search = event.target.value; this.pageIndex = 0; this.renderTable(); });
        this.root.on('click', '[data-step]', (event) => { this.pageIndex += Number(event.currentTarget.dataset.step); this.renderTable(); });
        page.set_primary_action('تحديث البيانات', () => this.refresh(), 'refresh');
        page.add_inner_button('فتح التقرير / تصدير', () => {
            frappe.route_options = this.filters();
            frappe.set_route('query-report', 'Crane Profit Distribution');
        });
        frappe.after_ajax(() => { this.ready = true; this.refresh(); });
    }
    t(value) {
        if (!value) return '';
        if (CraneDistributionDashboard.labels[value]) return CraneDistributionDashboard.labels[value];
        let text = __(value);
        Object.entries(CraneDistributionDashboard.labels).filter(([key]) => key.length > 70).forEach(([key, translation]) => { text = text.replace(key, translation); });
        return text;
    }
    esc(value) { return frappe.utils.escape_html(String(value ?? '')); }
    money(value, currency) { return this.esc(new Intl.NumberFormat('ar-EG', {style: 'currency', currency: currency || this.data.currency, minimumFractionDigits: this.data.precision ?? 2, maximumFractionDigits: this.data.precision ?? 2}).format(Number(value) || 0)); }
    defaults() {
        return {company: frappe.defaults.get_user_default('Company'), view: 'Distribution Details', report_date: frappe.datetime.get_today(), date_basis: 'Work Period', from_date: frappe.datetime.month_start(), to_date: frappe.datetime.get_today(), settlement_status: 'Submitted', participant: 'All'};
    }
    addFilters() {
        const select = (values) => values.map(value => ({value, label: value ? this.t(value) : 'كل الحالات'}));
        const fields = [
            ['company', 'الشركة', 'Link', 'Company'], ['from_date', 'من تاريخ', 'Date'], ['to_date', 'إلى تاريخ', 'Date'],
            ['report_date', 'الرصيد حتى تاريخ', 'Date'], ['crane', 'الونش', 'Link', 'Crane'], ['shareholder', 'الشريك', 'Link', 'Shareholder'],
            ['settlement_status', 'حالة التسوية', 'Select', select(['Submitted', 'Draft', 'All'])],
            ['payment_status', 'حالة المستحقات', 'Select', select(['', 'Unpaid', 'Partly Paid', 'Paid', 'No Entitlement', 'Draft', 'Awaiting Invoice'])],
            ['view', 'طريقة عرض التفاصيل', 'Select', select(['Settlement Summary', 'Participant Summary', 'Distribution Details', 'Source Details', 'Entitlement Movements'])],
            ['date_basis', 'اختيار الفترة حسب', 'Select', select(['Work Period', 'Settlement Posting Date'])],
            ['participant', 'الأطراف المعروضة', 'Select', select(['All', 'Our Company', 'External Partners'])],
            ['settlement', 'التسوية', 'Link', 'Crane Profit Settlement'], ['assignment', 'أمر الإيجار', 'Link', 'Rental Contract'],
            ['timesheet', 'سجل العمل', 'Link', 'Crane Timesheet'], ['sales_invoice', 'فاتورة البيع', 'Link', 'Sales Invoice'], ['customer', 'العميل', 'Link', 'Customer']
        ];
        const defaults = this.defaults();
        fields.forEach(([fieldname, label, fieldtype, options], index) => {
            const holder = $('<div>').appendTo(this.root.find(index < 10 ? '.cdd-filters:first' : '.cdd-advanced'));
            const control = frappe.ui.form.make_control({parent: holder, render_input: true, df: {
                fieldname, label, fieldtype, options, reqd: ['company', 'report_date'].includes(fieldname),
                change: async () => {
                    if (!this.ready) return;
                    if (fieldname === 'company') {
                        this.ready = false;
                        await Promise.all(['shareholder', 'crane', 'settlement', 'assignment', 'timesheet', 'sales_invoice', 'customer'].map(key => this.controls[key].set_value('')));
                        this.ready = true;
                    }
                    clearTimeout(this.timer);
                    this.timer = setTimeout(() => this.refresh(), 250);
                }
            }});
            if (['shareholder', 'settlement', 'assignment', 'sales_invoice'].includes(fieldname)) {
                control.get_query = () => ({filters: {company: this.controls.company.get_value()}});
            }
            this.controls[fieldname] = control;
            if (defaults[fieldname]) control.set_value(defaults[fieldname]);
        });
    }
    filters() { return Object.fromEntries(Object.entries(this.controls).map(([key, control]) => [key, control.get_value()])); }
    async reset() {
        this.ready = false;
        const defaults = this.defaults();
        await Promise.all(Object.entries(this.controls).map(([key, control]) => control.set_value(defaults[key] || '')));
        this.ready = true;
        this.search = '';
        this.refresh();
    }
    async refresh() {
        const id = ++this.request;
        const filters = this.filters();
        this.root.find('.cdd-results').empty();
        this.root.find('.cdd-count').text('—');
        if (!filters.company || !filters.report_date) {
            this.root.find('.cdd-feedback').text('اختر الشركة وتاريخ الرصيد لعرض البيانات.');
            return;
        }
        this.root.attr('aria-busy', 'true');
        this.root.find('.cdd-feedback').text('جارٍ تحميل المستحقات وتفاصيل الشراكة…');
        try {
            const response = await frappe.call({method: 'heavy_equipment_rental.distribution_dashboard.get_data', args: {filters}});
            if (id !== this.request) return;
            this.data = response.message;
            this.pageIndex = 0;
            this.render();
            this.root.find('.cdd-feedback').text(`تم تحديث البيانات • ${new Date().toLocaleTimeString('ar-EG')}`);
        } catch (error) {
            if (id === this.request) this.root.find('.cdd-feedback').text('تعذر تحميل البيانات. راجع الفلاتر والصلاحيات ثم اضغط تحديث البيانات.');
        } finally {
            if (id === this.request) this.root.attr('aria-busy', 'false');
        }
    }
    render() {
        const data = this.data;
        this.root.find('.cdd-count').text(`${data.settlement_count} تسوية`);
        const colors = {Blue: 'blue', Green: 'green', Orange: 'orange', Red: 'red', Gray: 'gray'};
        const cards = data.cards.map((card, index) => `<article class="cdd-card ${colors[card.indicator] || 'blue'}" style="--delay:${index * 25}ms"><span>${this.esc(this.t(card.label))}</span><strong>${this.money(card.value, card.currency)}</strong></article>`).join('');
        const total = Object.values(data.statuses).reduce((sum, value) => sum + value, 0);
        const statuses = Object.entries(data.statuses).map(([status, count]) => `<button class="cdd-status" data-status="${this.esc(status)}"><span>${this.badge(status)} <b>${count}</b></span><span class="cdd-track"><span style="width:${total ? count / total * 100 : 0}%"></span></span></button>`).join('');
        this.root.find('.cdd-results').html(`<div class="cdd-cards">${cards}</div>
            <section class="cdd-panel"><h3>حالات مستحقات الشركاء</h3><p class="text-muted">عدد استحقاقات الشركاء في التسويات المختارة؛ قد يظهر الشريك في أكثر من تسوية. اضغط على الحالة لتصفيتها.</p><div class="cdd-statuses">${statuses || '<p>لا توجد مستحقات شركاء ضمن الاختيار الحالي.</p>'}</div></section>
            <details class="cdd-panel cdd-notes"><summary>كيف تُقرأ هذه الأرقام؟</summary><p>${this.esc(this.t(data.message))}</p><p>بطاقات الإيراد والتكاليف ونصيب الشركة تعرض التسويات المختارة كاملة. فلتر الطرف يخص صفوف التفاصيل؛ المسودات تقديرية، ونصيب الشركة ليس رصيد خزينة.</p></details>
            <section class="cdd-panel"><div class="cdd-table-head"><h3>${this.esc(this.t(this.controls.view.get_value()))}</h3><input class="form-control cdd-search" type="search" aria-label="بحث داخل التفاصيل" placeholder="ابحث داخل التفاصيل…" value="${this.esc(this.search)}"></div><div class="cdd-table-region"></div></section>`);
        this.renderTable();
    }
    badge(status) {
        const color = {'Paid': 'green', 'Partly Paid': 'orange', 'Unpaid': 'red', 'Retained by Company': 'blue', 'مدفوع': 'green', 'مدفوع جزئيًا': 'orange', 'غير مدفوع': 'red'}[status] || 'gray';
        return `<span class="cdd-badge ${color}">${this.esc(this.t(status))}</span>`;
    }
    cell(column, row) {
        const value = row[column.fieldname];
        if (value === undefined || value === null || value === '') return '—';
        if (['status', 'settlement_status'].includes(column.fieldname)) return this.badge(value);
        if (column.fieldtype === 'Currency') return `<span class="cdd-number">${this.money(value, row.currency)}</span>`;
        if (column.fieldtype === 'Percent') return `${this.esc(value)}٪`;
        if (column.fieldtype === 'Date') return this.esc(frappe.datetime.str_to_user(value));
        if (['Link', 'Dynamic Link'].includes(column.fieldtype) && column.options !== 'DocType') {
            const doctype = column.fieldtype === 'Dynamic Link' ? row[column.options] : column.options;
            if (doctype) return `<a href="${this.esc(frappe.utils.get_form_link(doctype, String(value)))}">${this.esc(value)}</a>`;
        }
        return this.esc(this.t(String(value)));
    }
    renderTable() {
        const cols = this.data.columns.filter(col => !col.hidden);
        const rows = this.data.rows.filter(row => !row.is_total_row && (!this.search || cols.some(col => String(this.t(String(row[col.fieldname] ?? ''))).toLocaleLowerCase().includes(this.search.toLocaleLowerCase()))));
        const pages = Math.max(1, Math.ceil(rows.length / 25));
        this.pageIndex = Math.max(0, Math.min(this.pageIndex, pages - 1));
        const visible = rows.slice(this.pageIndex * 25, (this.pageIndex + 1) * 25);
        this.root.find('.cdd-table-region').html(rows.length ? `<p class="text-muted">${rows.length} صف • اسحب الجدول أفقيًا لعرض باقي التفاصيل</p><div class="cdd-scroll" tabindex="0" role="region" aria-label="جدول تفاصيل المستحقات"><table><thead><tr>${cols.map(col => `<th scope="col">${this.esc(this.t(col.label))}</th>`).join('')}</tr></thead><tbody>${visible.map(row => `<tr>${cols.map(col => `<td>${this.cell(col, row)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="cdd-pagination"><button class="btn btn-default btn-sm" data-step="-1" ${this.pageIndex === 0 ? 'disabled' : ''}>السابق</button><span>صفحة ${this.pageIndex + 1} من ${pages}</span><button class="btn btn-default btn-sm" data-step="1" ${this.pageIndex + 1 >= pages ? 'disabled' : ''}>التالي</button></div>` : '<div class="cdd-empty"><h3>لا توجد نتائج مطابقة</h3><p>جرّب توسيع الفترة أو إزالة فلتر الحالة أو الشريك أو كلمة البحث.</p></div>');
    }
}

CraneDistributionDashboard.labels = {
    "Account": "الحساب",
    "Company": "الشركة",
    "Crane": "المعدة",
    "Rental Contract": "تخصيص المعدات",
    "Crane Name": "اسم المعدة",
    "Crane Timesheet": "سجل ساعات المعدة",
    "Customer": "العميل",
    "Description": "الوصف",
    "Draft": "مسودة",
    "Expense Entry": "قيد المصروفات",
    "Expense Entry Type": "نوع قيد المصروفات",
    "Journal Entry": "قيد اليومية",
    "Sales Invoice": "فاتورة البيع",
    "Submitted": "معتمدة",
    "Total": "الإجمالي",
    "Remaining Balance %": "نسبة توزيع المتبقي %",
    "Operating Share": "مستحق التشغيل",
    "Remaining Balance Share": "نصيب المتبقي",
    "Crane Profit Settlement": "تسوية مستحقات الكرين",
    "Shareholder": "الشريك",
    "Posted Entitlement": "المستحق المرحل",
    "Pending Entitlement": "مستحق تحت الاعتماد",
    "Outstanding": "المتبقي",
    "Entitlement Status": "حالة الاستحقاق",
    "Awaiting Invoice": "بانتظار اعتماد الفاتورة",
    "Unpaid": "غير مدفوع",
    "Partly Paid": "مدفوع جزئيًا",
    "Paid": "مدفوع",
    "No Entitlement": "لا توجد مستحقات",
    "Partner Name": "اسم الشريك",
    "Movement": "الحركة",
    "Entitlement": "استحقاق",
    "Payment / Adjustment": "دفع / تسوية",
    "Settlement Summary": "ملخص التسويات",
    "Distribution Details": "تفاصيل توزيع الأرباح",
    "Source Details": "مصادر الإيرادات والمصروفات",
    "Entitlement Movements": "حركة الاستحقاق والسداد",
    "Work Period": "فترة العمل",
    "Settlement Posting Date": "تاريخ ترحيل التسوية",
    "Settlement Status": "حالة التسوية",
    "Participant": "الطرف",
    "External Partners": "الشركاء الخارجيون",
    "External Partner": "شريك خارجي",
    "Participant Name": "اسم الطرف",
    "Our Company": "شركتنا",
    "Retained by Company": "محتفظ به للشركة",
    "Settlement Revenue": "إيراد التسوية",
    "Posted Settlement Revenue": "إيراد التسويات المعتمدة",
    "Settlement Costs": "مصروفات التسوية",
    "Total Operating Share": "إجمالي حصة التشغيل",
    "After Operating Share": "المتبقي بعد التشغيل",
    "Residual Pool": "المتاح لتوزيع المتبقي",
    "Company Operating Share": "نصيب الشركة من التشغيل",
    "Company Residual Share": "نصيب الشركة من المتبقي",
    "Company Total Retention": "إجمالي نصيب الشركة",
    "Partners Calculated Share": "نصيب الشركاء المحتسب",
    "Partners Posted Entitlement": "استحقاق الشركاء المرحل",
    "Draft Partner Estimates": "تقديرات الشركاء غير المرحلة",
    "Partner Payments": "مدفوعات الشركاء",
    "Other Partner Adjustments": "تسويات الشركاء الأخرى",
    "Partners Outstanding": "المتبقي للشركاء",
    "Filtered Partners Entitlement": "استحقاق الشركاء المحددين",
    "Filtered Partners Paid / Adjusted": "المسدد والمسوى للشركاء المحددين",
    "Filtered Partners Outstanding": "المتبقي للشركاء المحددين",
    "Expense Burden": "أثر المصروفات على النصيب",
    "Residual Before These Costs": "نصيب المتبقي قبل هذه المصروفات",
    "Total Share": "إجمالي النصيب",
    "Ownership %": "نسبة الملكية %",
    "Source Posting Date": "تاريخ ترحيل المصدر",
    "Source Type": "نوع المصدر",
    "Source Document": "مستند المصدر",
    "Allocated Revenue": "الإيراد المخصص للتسوية",
    "Allocated Cost": "التكلفة المخصصة للتسوية",
    "Source Amount (Reference)": "مبلغ المصدر للمرجعية",
    "Allocation Basis": "أساس التخصيص",
    "Movement Date": "تاريخ الحركة",
    "Entitlement Increase": "زيادة الاستحقاق",
    "Settlement / Payment Decrease": "تخفيض بالسداد أو التسوية",
    "Partner Settlement Balance": "رصيد الشريك في التسوية",
    "Entitlement Journal": "قيد الاستحقاق",
    "Work From": "العمل من",
    "Work To": "العمل إلى",
    "Company and Balance As Of are required.": "الشركة وتاريخ الرصيد مطلوبان.",
    "From Date must be before Balance As Of.": "بداية الفترة يجب ألا تتجاوز تاريخ الرصيد.",
    "To Date must be before Balance As Of.": "نهاية الفترة يجب ألا تتجاوز تاريخ الرصيد.",
    "Select a Shareholder in the report Company.": "اختر شريكًا في شركة التقرير.",
    "Whole saved settlements are selected by overlapping work dates or settlement posting date; amounts are not prorated by report filters. Summary cards include each selected settlement once. Company retention is not a cash balance. Paid / Adjusted and outstanding use the native payment ledger through Balance As Of. Drafts are estimates, not posted entitlements.": "يعرض التقرير التسويات المحفوظة كاملة حسب تداخل فترة العمل أو تاريخ الترحيل، ولا يعيد توزيع مبالغها حسب فلاتر الفترة. البطاقات تجمع كل تسوية مرة واحدة. نصيب الشركة ليس رصيد نقدية. السداد والتسويات والأرصدة من دفتر الدفع حتى تاريخ الرصيد. المسودات تقديرات وليست استحقاقات مرحلة.",
    "Partner and payment-status filters select matching settlements. Summary cards retain the full settlement context; Distribution Details and Entitlement Movements show only matching external partners. Source Details includes all selected settlement sources.": "فلتر الشريك وحالة السداد يحدد التسويات المطابقة. البطاقات تعرض إجمالي هذه التسويات، بينما تفاصيل التوزيع والحركة تعرض الشركاء الخارجيين المطابقين فقط. مصادر الإيرادات والمصروفات تعرض كامل مصادر التسويات المختارة.",
    "Some saved source postings are later than Balance As Of; this report preserves the settlement snapshot rather than reconstructing an earlier cost estimate.": "بعض مصادر التسوية المحفوظة تاريخ ترحيلها بعد تاريخ الرصيد؛ التقرير يعرض لقطة التسوية المحفوظة ولا يعيد بناء تقدير التكاليف بتاريخ سابق.",
    "Draft figures are the last saved calculation. Recalculate the settlement after changing sources; the report does not refresh or post it.": "أرقام المسودات هي آخر حساب محفوظ. أعد حساب التسوية بعد تعديل مصادرها؛ التقرير لا يعيد حسابها ولا يرحلها.",
    "Participant Summary": "ملخص الشركة والشركاء",
    "Settlement Count": "عدد التسويات",
    "Expense Burden compares rounded residual shares before and after saved costs, after prior losses. Deficit drafts may contain costs beyond the distributable pool. This is explanatory, not another expense posting. Ownership % and Remaining Balance % are independent.": "أثر المصروفات يقارن نصيب المتبقي المقرب قبل التكاليف وبعدها، بعد الخسائر السابقة. قد تحتوي المسودات العاجزة على تكاليف تتجاوز وعاء التوزيع. هذا شرح للحساب وليس قيد مصروف إضافيًا. نسبة الملكية مستقلة عن نسبة توزيع المتبقي.",
    "Rental Contract": "أمر الإيجار",
    "Expense Type": "نوع المصروف",
    "Income Account": "حساب الإيراد",
    "Loss Brought Forward": "الخسائر المرحلة",
    "Operating %": "نسبة التشغيل",
    "Service From Date": "بداية فترة الخدمة",
    "Service To Date": "نهاية فترة الخدمة",
    "Settlement": "التسوية",
    "Timesheet": "سجل العمل",
    "Voucher": "المستند",
    "Voucher Type": "نوع المستند",
    "All": "الكل",
    "Payment Entry": "سند الدفع"
};
