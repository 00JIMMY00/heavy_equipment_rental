const today = frappe.datetime.get_today();
const company = frappe.defaults.get_user_default("Company") || frappe.boot.sysdefaults.company || __COMPANY_JSON__;
const currency = __CURRENCY_JSON__;
const monthStart = today.slice(0, 7) + "-01";
const number = new Intl.NumberFormat(frappe.boot.lang || "en", { maximumFractionDigits: 2 });
const count = new Intl.NumberFormat(frappe.boot.lang || "en", { maximumFractionDigits: 0 });

root_element.querySelector("[data-company]").textContent = company;
root_element.querySelector("[data-asof]").textContent = "As of " + frappe.datetime.str_to_user(today);

function metric(key, doctype, fn, field, filters, money = true) {
  const target = root_element.querySelector(`[data-kpi="${key}"]`);
  const doc = { document_type: doctype, function: fn, aggregate_function_based_on: field };
  frappe.xcall("frappe.desk.doctype.number_card.number_card.get_result", { doc, filters })
    .then(value => {
      const result = Number(value || 0);
      target.textContent = money ? `${number.format(result)} ${currency}` : count.format(result);
    })
    .catch(() => {
      target.textContent = "—";
      target.title = "This metric is unavailable with your current permissions.";
    });
}

const salesBase = [["Sales Invoice", "company", "=", company], ["Sales Invoice", "docstatus", "=", 1], ["Sales Invoice", "is_return", "=", 0]];
const purchaseBase = [["Purchase Invoice", "company", "=", company], ["Purchase Invoice", "docstatus", "=", 1], ["Purchase Invoice", "is_return", "=", 0]];
metric("sales", "Sales Invoice", "Sum", "base_grand_total", [...salesBase, ["Sales Invoice", "posting_date", ">=", monthStart], ["Sales Invoice", "posting_date", "<=", today]]);
metric("purchases", "Purchase Invoice", "Sum", "base_grand_total", [...purchaseBase, ["Purchase Invoice", "posting_date", ">=", monthStart], ["Purchase Invoice", "posting_date", "<=", today]]);

// outstanding_amount is in the invoice currency, so restrict balances to the company's currency.
const salesDue = [...salesBase, ["Sales Invoice", "currency", "=", currency], ["Sales Invoice", "outstanding_amount", ">", 0]];
const purchaseDue = [...purchaseBase, ["Purchase Invoice", "currency", "=", currency], ["Purchase Invoice", "outstanding_amount", ">", 0]];
metric("receivable", "Sales Invoice", "Sum", "outstanding_amount", salesDue);
metric("payable", "Purchase Invoice", "Sum", "outstanding_amount", purchaseDue);
metric("overdue_sales", "Sales Invoice", "Count", null, [...salesDue, ["Sales Invoice", "due_date", "<", today]], false);
metric("overdue_purchases", "Purchase Invoice", "Count", null, [...purchaseDue, ["Purchase Invoice", "due_date", "<", today]], false);
