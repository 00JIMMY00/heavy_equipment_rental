/* Enhance native Workspace blocks; the native editor remains the source of truth. */
(() => {
  const route = 'Workspaces/Crane Operations';
  const colors = ['#2864ed', '#813df5', '#059669', '#f5660b', '#0891b2', '#db2777', '#5546ed', '#0d9488'];
  let counts;
  let scheduled = false;

  function localizeLinkStatus() {
    if (frappe.boot.lang !== 'ar') return;
    document.querySelectorAll('.awesomplete .visually-hidden[role="status"]').forEach(el => {
      const value = el.textContent.trim();
      let translated;
      if (value === 'Begin typing for results.') translated = 'ابدأ الكتابة لعرض النتائج.';
      else if (value === 'No results found') translated = 'لا توجد نتائج';
      else if (/^\d+ results found$/.test(value)) translated = value.split(' ')[0] + ' نتائج مطابقة';
      else if (/^Type \d+ or more characters for results\.$/.test(value)) translated = 'اكتب ' + value.split(' ')[1] + ' أحرف على الأقل لعرض النتائج.';
      if (translated) el.textContent = translated;
    });
  }

  function enhance() {
    scheduled = false;
    localizeLinkStatus();
    const active = frappe.get_route_str() === route;
    document.body.classList.toggle('her-operations-reference', active);
    if (!active) return;
    const page = $('.page-container:visible');
    if (frappe.boot.lang === 'ar') {
      const replacements = [['.her-overview-title', 'Crane Operations'], ['.her-overview-subtitle', 'Workspace overview'], ['.her-all-workspaces', 'All workspaces']];
      replacements.forEach(([selector, source]) => {
        const el = page.find(selector);
        if (el.text().trim() === source) el.text(__(source));
      });
    }
    const editing = page.find('.layout-main-section.edit-mode').length > 0;
    page.find('.her-cranes-banner').attr({role: 'img', 'aria-label': __('Cranes')});
    page.find('.links-widget-box').each(function (index) {
      this.style.setProperty('--section-accent', colors[index % colors.length]);
    });
    page.find('.shortcut-widget-box').each(function (index) {
      this.style.setProperty('--section-accent', colors[index % colors.length]);
    });
    if (editing) return;
    const doctypes = frappe.boot.user.can_read || [];
    page.find('.links-widget-box .link-item').each(function () {
      if (this.querySelector('.her-link-icon')) return;
      const href = this.getAttribute('href') || '';
      const doctype = doctypes.find(name => href === '/app/' + frappe.router.slug(name));
      const single = doctype && frappe.boot.single_types.includes(doctype);
      const icon = document.createElement('span');
      icon.className = 'her-link-icon';
      icon.innerHTML = frappe.utils.icon(doctype && !single ? 'list' : 'file', 'xs');
      this.prepend(icon);
      if (!doctype || single) return;
      const badge = document.createElement('span');
      badge.className = 'her-link-count';
      badge.textContent = '…';
      badge.title = __('Total records you can access');
      this.append(badge);
      if (!counts) counts = frappe.xcall('heavy_equipment_rental.workspace.get_operations_counts').catch(() => ({}));
      counts.then(values => {
        const count = values[doctype];
        if (count == null) badge.remove();
        else {
          badge.textContent = String(count);
          this.classList.add('her-has-count');
        }
      });
    });
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(enhance, 80);
  }
  $(document).ready(() => {
    new MutationObserver(schedule).observe(document.getElementById('body') || document.body, {childList: true, subtree: true});
    frappe.router.on('change', schedule);
    schedule();
  });
})();
