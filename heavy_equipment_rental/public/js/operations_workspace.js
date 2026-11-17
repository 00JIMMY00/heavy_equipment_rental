/* Enhance native Workspace blocks; the native editor remains the source of truth. */
(() => {
  const route = 'Workspaces/Crane Operations';
  const colors = ['#2864ed', '#813df5', '#059669', '#f5660b', '#0891b2', '#db2777', '#5546ed', '#0d9488'];
  const mobileNavigation = window.matchMedia('(max-width: 991px)');
  let workspaceNavigation;
  let counts;
  let scheduled = false;

  function prepareNavigation(page) {
    const toggle = page.querySelector('.sidebar-toggle-btn');
    const column = page.querySelector('.layout-side-section');
    const panel = column?.querySelector('.overlay-sidebar');
    const content = page.querySelector('.layout-main-section-wrapper');
    if (!toggle || !panel || !content) return;

    const scrim = document.createElement('div');
    scrim.className = 'her-workspace-scrim';
    column.append(scrim);
    panel.id = 'her-workspace-navigation';
    panel.setAttribute('role', 'navigation');
    panel.setAttribute('aria-label', __('All workspaces'));
    toggle.setAttribute('aria-controls', panel.id);

    const active = () => frappe.get_route_str() === route;
    const sync = () => {
      if (!active()) {
        toggle.removeAttribute('aria-expanded');
        content.inert = false;
        return;
      }
      const open = mobileNavigation.matches
        ? panel.classList.contains('her-workspace-nav-open')
        : getComputedStyle(column).display !== 'none';
      toggle.setAttribute('aria-expanded', String(open));
      content.inert = mobileNavigation.matches && open;
    };
    const close = (restoreFocus = false) => {
      panel.classList.remove('her-workspace-nav-open');
      if (restoreFocus) toggle.focus();
      sync();
    };
    toggle.addEventListener('click', event => {
      if (!active()) return;
      event.stopImmediatePropagation();
      if (mobileNavigation.matches) panel.classList.toggle('her-workspace-nav-open');
      else $(column).toggle();
      sync();
    }, true);
    scrim.addEventListener('click', () => close(true));
    panel.addEventListener('click', event => {
      if (active() && mobileNavigation.matches && event.target.closest('.item-anchor')) close();
    });
    document.addEventListener('keydown', event => {
      if (active() && event.key === 'Escape' && panel.classList.contains('her-workspace-nav-open')) {
        event.preventDefault();
        event.stopPropagation();
        close(true);
      }
    }, true);
    mobileNavigation.addEventListener('change', () => close());
    return {close, sync};
  }

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
    if (!active) {
      workspaceNavigation?.close();
      return;
    }
    const workspace = document.getElementById('page-Workspaces');
    if (!workspaceNavigation && workspace) workspaceNavigation = prepareNavigation(workspace);
    workspaceNavigation?.sync();
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
