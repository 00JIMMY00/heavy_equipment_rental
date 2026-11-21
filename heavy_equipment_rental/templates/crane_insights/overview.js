const find = selector => root_element.querySelector(selector);
const locale = frappe.boot.lang || "en";
const number = new Intl.NumberFormat(locale, {maximumFractionDigits: 1});
const date = value => new Intl.DateTimeFormat(locale, {month: "short", day: "numeric", year: "numeric"})
    .format(new Date(value + "T12:00:00"));
const colors = {Operational: "#f4bd24", Maintenance: "#c96a16", Inactive: "#657389"};
const make = (tag, className, text) => {
    const el = document.createElement(tag);
    el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
};
find(".insights").dir = document.documentElement.dir || "ltr";
root_element.querySelectorAll("[data-t]").forEach(el => el.textContent = __(el.dataset.t));
find(".periods").setAttribute("aria-label", __("Reporting period"));
let request = 0;

function metrics(data) {
    const cards = find(".metrics");
    cards.replaceChildren();
    const work = data.work;
    const expenses = data.expenses;
    const restricted = __("Grouped Expense access required");
    const values = [
        ["Crane-linked expenses", expenses && amounts(expenses.totals), restricted],
        ["Expense batches", expenses?.batches, restricted],
        ["Expense lines", expenses?.rows.length, restricted],
        ["Cranes with expenses", expenses?.charged_cranes, restricted],
        ["Fleet size", data.fleet],
        ["Operational", data.conditions.Operational || 0],
        ["Billable hours", work?.hours, __("Timesheet access required")],
        ["Working cranes", work?.active, __("Timesheet access required")],
    ];
    for (const [label, value, reason] of values) {
        const card = make("div", "metric");
        const display = typeof value === "number" ? number.format(value) : value;
        card.append(make("span", "label-line", __(label)), make("strong", "", display ?? "—"));
        if (value == null) card.append(make("small", "", reason));
        cards.append(card);
    }
}

function amounts(totals) {
    const parts = Object.entries(totals).sort(([a], [b]) => a.localeCompare(b));
    return parts.map(([currency, value]) => new Intl.NumberFormat(locale, {
        style: "currency", currency, currencyDisplay: "code"
    }).format(value)).join(" / ") || number.format(0);
}

function expenseLedger(data) {
    const ledger = find(".expense-ledger");
    ledger.replaceChildren();
    find(".expense-period").textContent = date(data.start) + " – " + date(data.as_of);
    const byCrane = new Map();
    for (const row of data.expenses?.rows || []) {
        if (!byCrane.has(row.crane)) byCrane.set(row.crane, []);
        byCrane.get(row.crane).push(row);
    }
    if (!data.expenses) ledger.append(make("p", "empty", __("Grouped Expense access required")));
    if (!data.cranes.length) ledger.append(make("p", "empty", __("No visible cranes.")));
    const cranes = [...data.cranes].sort((a, b) => Number(byCrane.has(b.name)) - Number(byCrane.has(a.name)));
    for (const crane of cranes) {
        const rows = byCrane.get(crane.name) || [];
        const totals = {};
        for (const row of rows) totals[row.currency] = (totals[row.currency] || 0) + Number(row.amount);
        const entry = make(rows.length ? "details" : "div", "ledger-entry");
        const head = make(rows.length ? "summary" : "div", "crane-row");
        const name = make("span", "crane-name", crane.crane_name || crane.name);
        if (crane.crane_name && crane.crane_name !== crane.name) name.append(make("small", "", crane.name));
        head.append(name, make("span", "line-count", data.expenses ? __("{0} lines", [number.format(rows.length)]) : "—"),
            make("b", "amount", data.expenses ? amounts(totals) : "—"));
        entry.append(head);
        for (const row of rows) {
            const line = make("div", "expense-line");
            const source = make("a", "", row.name);
            source.href = "/app/grouped-expense/" + encodeURIComponent(row.name);
            const label = make("span", "", row.description || __("Grouped Expense"));
            label.append(make("small", "", date(row.posting_date) + " · "), source);
            line.append(label, make("b", "amount", amounts({[row.currency]: Number(row.amount)})));
            entry.append(line);
        }
        ledger.append(entry);
    }
}

function condition(data) {
    const target = find(".condition");
    const bar = make("div", "condition-bar");
    target.replaceChildren(bar);
    for (const key of new Set([...Object.keys(colors), ...Object.keys(data.conditions)])) {
        const count = data.conditions[key] || 0;
        const segment = make("i", "");
        segment.style.width = (data.fleet ? 100 * count / data.fleet : 0) + "%";
        segment.style.background = colors[key] || "#a2aab0";
        bar.append(segment);
        const row = make("div", "row");
        const label = make("span", "");
        const dot = make("i", "dot");
        dot.style.background = segment.style.background;
        label.append(dot, document.createTextNode(__(key)));
        row.append(label, make("b", "", number.format(count)));
        target.append(row);
    }
}

function activity(data) {
    const plot = find(".plot");
    const leaders = find(".leaders");
    plot.replaceChildren();
    leaders.replaceChildren();
    if (!data.work || !data.work.hours) {
        const message = __(data.work ? "No billable hours in this period." : "Timesheet access required");
        for (const el of [plot, leaders]) el.append(make("p", "empty", message));
        return;
    }
    const series = data.work.daily;
    const peak = Math.max(...series);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 600 124");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", __("Peak daily billable hours") + " · " + number.format(peak));
    function shape(type, attrs) {
        const el = document.createElementNS(svg.namespaceURI, type);
        for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
        svg.append(el);
        return el;
    }
    for (const y of [5, 61, 117]) {
        shape("line", {x1: 0, x2: 600, y1: y, y2: y, stroke: "#dce0e6", "stroke-dasharray": "4 5"});
    }
    const points = series.map((hours, index) => (2 + index * 596 / (series.length - 1)) + "," + (117 - 112 * hours / peak)).join(" ");
    shape("polygon", {points: "2,117 " + points + " 598,117", fill: "#ffcc35", opacity: ".35"});
    shape("polyline", {points, fill: "none", stroke: "#ad7600", "stroke-width": 2.7, "vector-effect": "non-scaling-stroke"});
    const axis = make("div", "axis");
    axis.append(make("span", "", date(data.start)), make("span", "", date(data.as_of)));
    plot.append(make("small", "empty", __("Peak daily billable hours") + " · " + number.format(peak)), svg, axis);
    for (const crane of data.work.leaders) {
        const row = make("div", "leader");
        const link = make("a", "", crane.label);
        link.href = "/app/crane/" + encodeURIComponent(crane.name);
        const track = make("div", "track");
        const fill = make("i", "");
        fill.style.width = 100 * crane.hours / data.work.leaders[0].hours + "%";
        track.append(fill);
        row.append(link, track, make("b", "", number.format(crane.hours) + " " + __("hrs")));
        leaders.append(row);
    }
}

async function load(days) {
    const current = ++request;
    const notice = find(".notice");
    find(".results").hidden = true;
    notice.textContent = __("Loading fleet metrics…");
    find(".periods").querySelectorAll("button").forEach(button =>
        button.setAttribute("aria-pressed", String(Number(button.value) === days)));
    try {
        const response = await frappe.call({method: "heavy_equipment_rental.crane_insights.get_overview", args: {days}});
        if (current !== request) return;
        const data = response.message;
        metrics(data);
        activity(data);
        condition(data);
        expenseLedger(data);
        find(".stamp").textContent = __("Fleet snapshot") + " · " + date(data.as_of);
        notice.replaceChildren();
        find(".results").hidden = false;
    } catch {
        if (current !== request) return;
        notice.textContent = __("Fleet metrics could not be loaded.");
        const retry = make("button", "", __("Retry"));
        retry.onclick = () => load(days);
        notice.append(retry);
    }
}

for (const days of [7, 30, 90]) {
    const button = make("button", "", __("{0} days", [number.format(days)]));
    button.value = days;
    button.onclick = () => load(days);
    find(".periods").append(button);
}
load(30);
