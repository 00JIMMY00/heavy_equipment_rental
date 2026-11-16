# Project context

## 2026-11-16 — Crane ownership share bar

Replaced the Crane Ownership field’s plain classification and technical description with a segmented owner share bar. Each owner has a colored segment plus a name/percentage legend, using Shareholder titles when permitted. Updates on ownership, owner selection, add/remove and form refresh. Incomplete draft totals show an explicit warning. Classification, validation, ownership/profit calculations and historical agreements remain unchanged; no schema change.


## 2026-11-16 — Shallow regenerated panorama (latest)

Regenerated the crane image with distant vehicles and low booms composed for a shallow panoramic strip. The workspace now uses `cranes-panorama-v2.png`, displayed at 10:1 with a hard maximum height of 25vh/25svh and a focal position of 62%. This supersedes the tall 3:1 banner. Sections/الأقسام remains removed.


## 2026-11-16 — Full crane banner

Increased the crane banner from 10:1 to the image’s native 3:1 ratio and used contain sizing so all three cranes remain visible without cropping. Removed the Sections/الأقسام heading from the template and dev3’s saved workspace. Existing site edits are preserved.


## 2026-11-16 — Requested workspace wording and banner

Renamed Rental Operations in Arabic to «عمليات على الونش», with links ordered «سرك الونش», «صيانة الونش», «تكليف الونش». Removed the separate Maintenance card, Quick Access, overview text, top Customize/Refresh actions and bottom Timesheet/Maintenance reports. Added a generated crane photo displayed at approximately 10:1. Native bottom Edit remains available. Applied to dev3 after a private workspace backup; migration persistence remains unchanged.


## 2026-11-16 — Arabic interface audit

Extended the app Arabic catalog with current workspace, rental, maintenance, asset, settlement, payment and validation text. The reference workspace overview and custom actions now translate in Arabic mode. Arabic browser checks showed no English UI words in the workspace; the new Crane form labels also translated. Global Frappe/ERPNext labels use their installed Arabic catalogs. Stored user-entered names, IDs and currency symbols are data and remain as entered. Clear site cache after updating translations.


## 2026-11-16 — Reference-style workspace (latest)

Matched the supplied reference using a compact overview, Quick Access pills, eight native section cards in four desktop columns, colored markers, row icons and permission-filtered counts. Customize invokes native Edit; All workspaces toggles the navigation sidebar. Native card labels, links, order and widths remain editable and persist through migrations. The previous compact layout is backed up on dev3 to `private/backups/her-workspace-before-reference.json`. See [on-site editing instructions](WORKSPACE.md). This supersedes the six-panel arrangement below.


## 2026-11-16 — Compact workspace and slate-blue theme (latest)

Replaced the large welcome banner and repeated section descriptions with six compact frequent-action tiles, six native link panels (Billing, Treasury, Partners, Reports, Directory, Settings), and two report-builder shortcuts. All 28 destinations remain accessible. The shared theme now uses slate blue, a light navigation rail in light mode, coordinated dark surfaces and flatter controls. This supersedes the yellow/graphite theme and the spacious workspace arrangement below. Native Edit/Save and migration persistence remain in place. Applied the requested revision explicitly to dev3, backing up its prior layout to `private/backups/her-workspace-before-compact.json`; other initialized sites retain their arrangements.


## 2026-11-16 — Editable Crane Operations workspace

Crane Operations now groups native editable shortcuts into Daily Operations, Billing & Treasury, Partners & Profit Sharing, Reports, and Setup & Directory. Consistent card sizes, section descriptions and an industrial welcome panel support light/dark themes and mobile layouts. Added direct access to purchases, settlements, the distribution dashboard, suppliers and assets.

The layout is installed once from `heavy_equipment_rental/templates/crane_operations.json`. It is a site-owned Workspace (no Module), outside Frappe's standard workspace synchronization; later setup/migrations preserve site edits, including developer-mode edits. The first upgrade saves the complete previous Workspace to the site's private `backups/her-workspace-before-v2.json`. Existing workspace access roles remain unchanged. This supersedes the earlier instruction to retain the old workspace ordering. See [workspace editing](WORKSPACE.md).


- 2026-11-16: Removed the Crane Change Agreement shortcut. Edit terms and Agreement Effective From directly, then Save; dated history and server validation still apply. JavaScript syntax and whitespace checks passed; dev3 cache cleared.

## 2026-11-16 — Simple repair entry

The Maintenance form now offers Quick Repair (default), Use Stock Parts, and Supplier Bill. Quick Repair uses the HER company repair expense account and payment method, automatically resolving/creating its Expense Entry Type. Supplier Bill accepts stock parts and non-stock labour together; native purchase posting receives parts, and a Material Issue consumes only stock rows. Supplier payment defaults to full and supports partial/zero payment. Advanced Accounting retains capitalization, owner recovery, no-cost work and existing/manual documents. Legacy source values remain stored for compatibility; migration fills presentation choices without reposting or changing financial history. Mixed improvement bills use native Asset Repair service expenses plus stock consumption.

## 2026-11-16 — Maintenance form defaults

New Crane Maintenance records default Actual Start Date and Actual End Date to Today using native Date field defaults. Maintenance Type is removed from default list columns and retained on the form. Existing dates are preserved. Migrated dev3; verified new-document defaults/live metadata and all three rental workflow tests.

## 2026-11-15 — General Ledger rental filters

Crane/CPS GL filters also trace native Payment Entry References for source invoices/journals and settlement journals (complete payment vouchers, including shared payments). CPS-00008 Cash - T movement verified: receipt 3,600 less expenses 490 and partner payment 988.70 = 2,121.30. Select March 2–November 15 to include all four cash movements.

General Ledger now has Crane and Crane Profit Settlement (CPS) filters. CPS traces immutable source snapshots (Expense Entry → its native journal) plus its settlement journal; Crane traces linked native headers/items, expense journals and settlement snapshots. These are complete voucher filters, not prorated allocations. Native GL dates, account filters, permissions, currencies and totals remain in effect. No GL/schema/backfill changes.

- Expense Entry rental pickers now send only Posting Date, Crane, Company and an explicitly selected Assignment. No empty From/To filters appear. Work choices must include that one posting date; changing it refreshes/clears invalid selections. Maintenance behavior and submitted allocation snapshots are unchanged. Verified frontend filter arguments/date changes and native search against live Timesheet dates; syntax/whitespace checks passed. No schema change.

- Latest date clarification: Expense Entry uses Posting Date as its single expense date. Its legacy service From/To fields remain stored but hidden and ignored for expense date calculation; assignment/timesheet selection no longer fills a range. Explicit rental links remain authoritative. Maintenance retains Actual Start/End dates and its repair-period behavior. Historical submitted snapshots are preserved.

- Crane Operations tab and its shortcut panel removed at the user’s request. The form opens on Details; other tabs retain their order.

**Latest rule (2026-11-15):** Enable Profit Sharing and Hired from Supplier are mutually exclusive. Selecting either clears the other on the Crane form; server validation rejects both together. Both may remain off for ordinary company work. This supersedes earlier combined-hire/profit-sharing guidance. Existing agreements and posted documents are not rewritten.


## 2026-11-15 — Operating Fees table (latest)

- Crane uses Operating Fees rows: Our Company, Partner (Shareholder), Fee Basis and Operating Fee %. Default is Our Company / Grand Total / 0%. The previous single-recipient fields are hidden and retained for historical agreements.
- Grand Total means crane-allocated invoice revenue before expenses. Net Profit means positive Grand Total minus allocated expenses, before operating fees. Each row uses its own base independently; rates do not compound. Combined percentages cannot exceed 100%; settlement deficit controls still apply. Revenue remaining after fees and expenses follows Owners & Profit Shares.
- Fee rows are versioned with the agreement; settlement snapshots retain each base, rate and amount, and native partner entitlements combine operating fees and remaining-profit shares per recipient. Historical single-operator snapshots keep their original calculation and revenue basis. Migration exposes existing fees without reposting or rewriting history. New table-based agreements use Grand Total revenue for the distribution calculation.


## 2026-11-15 — Simplified crane ownership, operating fees and hire

- Owners & Profit Shares is the ownership source, including a default 100% Company row for new cranes. Ownership classification is calculated. The manual ownership type and new-agreement calculation selector are hidden; historical internal types and dated agreements remain available for compatibility.
- Hired from Supplier is independent of ownership and profit sharing. Supplier rates/units remain on Timesheets; supplier invoices are operating costs before residual profit distribution. Ordinary hire may leave ownership unrecorded.
- Operating Fee % and recipient replace ownership-dependent operator choices. External fee recipients may be any permitted Shareholder in the same Company, including someone outside the owners table. A company-only owner table can pay an external operating fee.
- Migration fills hire flags/classification and missing Company-owned rows without reposting transactions or changing historical agreement snapshots.

Routine Maintenance now supports Repair Source (My Stock / External Parts / External Service), item rows and native **Submit → Cancel → Amend** to post, reverse and correct native purchase/consumption documents from the same form. Cancellation previews dependencies and reverses them atomically; amendments clear generated links and repost corrected inputs. Historical completed/posted repairs become submitted without reposting. Connections links generated documents. HER Settings supplies company repair accounts, payment methods and optional maintenance warehouses. External purchases default to full supplier payment (editable to partial/zero). Repair Purpose supports routine expenses and asset improvements with the same automated completion flow, including native Asset Repair when required. Manual Documents explicitly labels the advanced/historical workflow; see [repair workflow](NATIVE_CRANE_WORKFLOW.md#repairs-including-company-owned-shared-and-external-cranes).

Rental cancellation uses the native **Cancel** button with a linked-document preview and an accounting reversal warning. Confirming cancels listed payments and dependencies atomically. Use native **Amend** for replacements; no extra correction buttons. See [instructions](USER_GUIDE.md#expense-and-settlement-corrections).


Payment Entry → **Get Outstanding Partner Entitlements** selects current open settlement balances for the selected Shareholder (or historical Supplier), company and payable account. Filter by settlement posting dates, Crane, Timesheet or Sales Invoice; add selected Journal Entry references without duplicates. A single payment can cover several settlements; partial amounts allocate in reference row order and each settlement retains its own native ledger balance/status.

**Arabic distribution dashboard:** `Crane Operations → Crane Distribution Dashboard` (`/app/crane-distribution-dashboard`) presents the comprehensive saved-settlement report with financial cards, status filtering and five searchable detail views. Uses the same calculation and permission checks; see [report guide](PROFIT_DISTRIBUTION_REPORT.md).

**Crane Profit Distribution** is the comprehensive saved-settlement report: settlement summary, company/partner totals, distribution percentages/cost burden, source details and native entitlement/payment movements. Company, work/posting dates, as-of balance date, Crane, Shareholder, status and document filters apply. Draft estimates stay separate from posted amounts; report cards count each selected settlement once. See [report guide](PROFIT_DISTRIBUTION_REPORT.md).

Crane Connections discovers direct links across standard/custom fields and child rows, including accounting dimensions, invoices, journals, payments and outgoing master/owner links. It uses the native dashboard with permission-filtered counts and matching list destinations; it also follows Asset acquisition, source invoices/journals and native payment references. A company leaf Cost Center selected only by this Crane contributes its attributed invoice/journal rows, including parts purchases; shared centers do not.

**Latest asset policy:** track Company assets only: Owned → full Company Asset; Shared → Company interest only; zero ownership → no Asset. Basis is automatic. Partners remain in ownership_partners, with no asset-value allocations. Earlier whole-crane/shared and custody descriptions below are superseded.

**Latest design (2026-11-13):** [Native Crane workflow](NATIVE_CRANE_WORKFLOW.md) supersedes the older whole-cost-only, per-crane Item assumptions below. Ownership contracts vary; accounting explicitly reviews whole-asset, company-interest or custody recognition. New cranes reuse a service Item. Repairs use native stock/service/asset/owner-invoice documents. The latest user instruction restores automatic source-revenue settlements on invoice submission, Invoice Grand Total and no depreciation deduction. Historical terms and ledgers remain intact.

Heavy Equipment Rental is a Frappe/ERPNext app for booking cranes, recording work, and billing rentals. The current user goal is a Crane-centered workflow coordinating native Assets, stock, repair accounting and owner settlements. Start from **Crane → Operations**; Assignment-first and Timesheet-first entry remain available.

- Assignment Details holds customer, location and the Assigned Cranes table with rental dates, billing unit, and agreed rate. Its date ranges prevent overlapping crane bookings. Its native Connections tab shows Cranes, Customer, Timesheets and Expense Entries. New Assignment rows default their visible billing unit/rate from HER Settings and Crane reference prices. Create → New Timesheet prompts for a crane when several distinct active cranes are booked and defaults editable period dates and agreed rental rate/unit from its booking (choose a period if that crane has multiple bookings).
- Timesheet is for one crane. New Timesheets prefill their selling unit from Settings and the matching reference price from the Crane; existing Assignment terms take precedence. Its period dates also become the rental dates when it creates an Assignment. Operator Shifts record work by ERPNext Employee; an optional default driver fills new rows, and each draft row can be changed through the editable Driver (Employee) selector directly in the grid.
- Rented Cranes link an ERPNext Supplier. Selecting one on a Timesheet defaults the editable Rented checkbox to checked. New Timesheets default their Supplier Billing UOM from Settings (Hour initially) and save it independently of selling terms. Checked Timesheets require a positive purchase price per selected supplier unit; submission creates and submits one Purchase Invoice for the Crane Item with that UOM. Hour counts distinct worked crane hours, Day counts distinct worked dates, and Month prorates worked dates by calendar month length. Unchecking skips purchasing. Supplier quantities use actual work, independent of the full date span or sales Billing Unit. Settings changes do not reinterpret saved purchase rates. Historical invoices and submitted snapshots are preserved; migration archives old terms and clears Day/Month purchase rates on drafts. Create → Payment on the Crane or submitted Timesheet opens a native draft supplier Payment Entry against an unpaid invoice.
- Timesheet Entries show the matching Assignment Rental Rate and Rental Rate Unit as read-only grid columns (Hour/Day/Month), alongside editable actual operating hours. Entered hours exclude downtime and are not overwritten when shift times change. The previous hourly-only field is retained internally for calculations. Timesheet shows hours by driver, a hard-copy attachment that remains available after submission, and Frappe's native Connections dashboard. Submitted work feeds draft Sales Invoices.
- Sales Invoices use normal customer receivables and payments. The invoice operator table and customer-to-driver direct-payment workflow were removed; Timesheet driver tracking and employee expense attribution remain independent. Migration archives retired invoice details/settings without changing posted accounting.
- Maintenance and Expense Entry costs require explicit rental links for CPS: a Timesheet charges only its settlement and fills Assignment; Assignment alone shares the cost across its submitted crane Timesheets by working hours. Neither link means a general, unallocated crane expense excluded from CPS. Dates do not choose or automatically fill the charged work. Mismatched links are rejected. Submitted settlement snapshots and ledgers remain unchanged; corrections use Cancel and Amend.
- Expense Entries can identify Crane and Assignment/Timesheet, with read-only Service From/To dates defaulted from the Assignment booking. Selecting an Assignment limits Crane choices to its active bookings; expense types and amounts edit inline in the expenses grid. Timesheet settlements deduct explicitly linked work costs independently of accounting and service dates, allocating Assignment costs once by submitted crane hours; closed allocations require reopening before changes. Existing posted settlements remain unchanged. See [PROFIT_SHARING.md](PROFIT_SHARING.md).
- Treasury Transaction transfers company-currency funds from a Mode of Payment default account to another cash/bank or explicitly designated treasury account. Optional Party Type/Party identify the recipient on the generated Journal Entry's destination debit row; native GL treasury balances retain no party. Submission posts a native Journal Entry; cancellation reverses it with normal accounting permissions.
- Crane Rental Profitability shows posted rental income, cash/custody expenses and supplier hire costs, and income minus expenses by company/posting date, with optional Assignment/Crane filters. The explicit development demo in `heavy_equipment_rental/demo.py` creates one complete cycle; see [SIMULATED_RENTAL.md](SIMULATED_RENTAL.md).
- Crane supports dated shared ownership and operating agreements with independent ownership/profit percentages. Matching percentages follow ownership edits in the form; new or changed agreements require explicit confirmation for an owner with zero remaining-profit share. Under Shared Ownership, Our Company may receive both an operating share and a partner residual share. Operated for Owner allows external partner rows only (`is_company = 0`); Our Company receives its operating share separately. The current business example has no taxes; invoice net and Grand Total coincide. Crane Profit Settlement closes consecutive periods, retains source/share snapshots, deducts an operating percentage from allocated invoice Grand Total before costs and residual distributions, blocks deficits, and posts external shares against source Income accounts through native supplier Journal Entries, with later Payment Entries for actual disbursement. Legacy net-profit agreements retain their configured allocation account. Optional Crane attribution on ordinary invoice items and journal rows covers additional revenue and costs. Existing rented-crane purchasing is unchanged. See [PROFIT_SHARING.md](PROFIT_SHARING.md).
- The custom `Crane Project` DocType was removed. ERPNext's native `Project` is separate from the rental workflow. Legacy project data was migrated to Assignment/Timesheet links before removal.
- The app also includes crane maintenance, expenses, and a rental calendar/timeline. It requires `arab_erp_theme` for the shared Expense Entry and Expense Entry Type DocTypes; the rental app adds optional Crane and Crane Assignment links to Expense Entry and integrates maintenance expenses. HER owns its industrial theme, logo, favicon, and loading assets, layered over the base theme without modifying its source or changing workspace structure.

Start with [README.md](../README.md). Core code is in `heavy_equipment_rental/heavy_equipment_rental/doctype/`, billing in `heavy_equipment_rental/billing.py`, and migrations in `heavy_equipment_rental/patches/` plus `heavy_equipment_rental/patches.txt`.

- Crane links one native ERPNext **Asset** per physical crane, separately from its rental service Item. Owned/shared Assets record the whole crane cost in company books; the live, permission-checked panel shows cost/current book value and reference shares from today's dated ownership percentages. Linking does not post money or infer contributions, payables or settlement depreciation. Accounting roles control links; uniqueness, quantity, company and custody-owner checks protect both Crane and native Asset edits. Existing Cranes remain unlinked until explicitly reviewed. See [Crane fixed assets](../README.md#crane-fixed-assets).

- Treasury workbook import is an explicit, audited development operation. The 172-row `الخزينه.xlsx` was posted to the new LYD company **شركة المعدات الثقيلة - ليبيا**, with zero starting balances and the user's approved date corrections. Expense Entries record operating costs; Treasury Transactions record funding, employee advances and owner drawings using explicitly designated balance-sheet accounts. **Crane Operations → Treasury Workbook** reproduces the seven-column RTL sheet from live posted GL entries, with source links and styled print/Excel exports. See [TREASURY_WORKBOOK.md](TREASURY_WORKBOOK.md) for reconciliation, account balances and the backed-up old-company reset.

- Treasury Transaction supports an optional company-specific **Cost Center** and copies it to new journal rows. Treasury Workbook has a **Cost Center** filter covering expenses, treasury and custody movements; filtered openings/totals apply to that center only. Imported transfers are linked to their explicit category centers without rewriting historical postings.

- New sharing Timesheets now create a linked draft **Crane Profit Settlement** automatically. Submitting their Sales Invoice automatically approves/posts the settlement and Shareholder entitlements in the same transaction. Company-specific Partners payable accounts default automatically. Settlement embeds payment balances/links and an unpaid-partner selector. Crane Partner Statement and Crane Partner Summary provide native-ledger movements, totals, payment status and aging. Historical supplier journals and period closures retain their original accounting; see the 2026-11-10 decisions and [PROFIT_SHARING.md](PROFIT_SHARING.md).

- Rental cancellation follows Timesheet → invoices → settlements. Invoice cancellation preserves submitted work; settlement cancellation preserves its invoice and work while reversing its own entitlement journal. The form previews and confirms the directed cancellation scope; server execution is atomic and retains accounting/payment guards.
