# Progress

## 2026-11-16 — Full-screen Arabic login (latest)

Browser verified a 1440×960 layout starting at (0, 0) and filling the viewport, Arabic by default with an English browser locale, forced light presentation with OS dark mode, 390px/320px layouts without overflow, keyboard password visibility, recovery and email-link navigation. No JavaScript errors; syntax and whitespace checks passed. Cleared dev3 website/cache and versioned assets.

Revised login to fill the viewport with white, pale sky blue and soft yellow, local crane photography and a locally hosted Cairo Arabic font (OFL). Arabic is the default for guest GET /login requests, even with English browser/cookie preferences; explicit _lang remains available. The request hook does not change stored user or site language settings. Login stays light regardless of the OS theme. Added conversational Arabic copy and retained native authentication, recovery, email-link and signup flows. Supersedes the centered navy login design. No schema migration required.

## 2026-11-16 — Unified Arabic Timesheet terminology

Browser verified Timesheet form tabs and workspace use «تايم شيت»; runtime translation checks cover main labels, plural, create action and legacy Work Log names. Audited all Timesheet/Work Log catalog entries for the canonical term. Timeline build and whitespace checks passed; site cache cleared.

Use «تايم شيت» consistently for Timesheet, Crane Timesheet, plural Timesheets, Crane Work Log and Equipment Work Log. Updated app translations, related messages, reports and timeline category. Legacy Arabic Timesheet labels resolve to the same wording, while Timeline retains «الجدول الزمني». Internal DocType names, IDs and data remain unchanged. Supersedes earlier «سرك» / «سجل العمل» terminology.

## 2026-11-16 — Compact crane timeline

Production build passed. Browser checked the exact ASG-00010 contract scope: two crane rows, November 3–7 with booking padding, Arabic controls and date labels, timeline beginning 206px from page top, activity toggle round trips, native detail link/Escape dismissal, collapsed filter controls and mobile without horizontal page overflow; no JavaScript errors. Removed zero-count activity controls after visual review. No documents changed.

Replaced the timeline hero, summary cards and repeated legends with a compact heading, period controls and counted activity toggles. Default grouping is one row per Crane. Contract-scoped URLs automatically fit the booked dates (one day padding, bounded to the existing 120-day range limit). Filters, search and custom dates are collapsed behind Filters. Timeline day columns fill available width for short bookings and scroll for long ranges; reduced sticky resource width. Clickable event details/native links and Escape dismissal remain available. Added Arabic timeline controls/date labels using the user's existing language, preserving theme and backend permission checks. No rental data or billing logic changed.

## 2026-11-16 — Rental Contract rename (latest)

Backed up dev3 before migration. Native DocType rename and saved workspace migration completed; all existing Timesheet/Expense/Maintenance rental links resolve, with no old Link targets left. Browser verified Arabic «عقد ايجار معدة», existing ASG-00008 opens with its crane rows, and new records default to RC-.#####. Twenty workflow tests ran: 19 passed, one legacy-column test skipped. Calendar production build and whitespace checks passed. Updated retained naming-series Property Setters to avoid ASG overriding the new RC default.

Renamed Crane Assignment in place to Rental Contract, Arabic «عقد ايجار معدة». A pre-model migration uses native DocType rename to retain existing IDs, child rows, permissions and all rental links. Existing ASG numbers remain valid; new documents use RC-.##### (legacy naming series remains accepted for saved records). Updated controllers, linked field labels/options, dashboards, workspace seed/saved links, reports, messages and calendar source. Stable internal assignment/crane_assignment fieldnames and API parameters remain for historical/integration compatibility; old Python controller imports forward to the new module. Current document route is /app/rental-contract. The old documentation below records prior milestones.

## 2026-11-16 — Full-width maintenance repair table

Browser verified visible table width 1218px inside the original 1258px Repair Items section. Four rental workflow tests passed; whitespace checks passed. No test form saved.

Removed the repair_column layout divider from Crane Maintenance. Items / Services spans the full width within the original Repair Items section; supplier details remain above the table. Section visibility rules and repair accounting behavior remain unchanged. Applied metadata migration to dev3.

## 2026-11-16 — Employee names in driver links

Applied on dev3. Browser verified TS-00010 Entries displays the Employee name on all four shifts while underlying links remain HR-EMP-00002; boot title configuration and whitespace checks passed. No document data changed.

Enabled Employee show_title_field_in_link using the existing employee_name title field. Native Employee Link controls and grid cells, including Timesheet Entries drivers, display employee names while saving the same Employee IDs. HER setup persists the Property Setter; existing payroll, shifts and employee references are untouched. Reload Desk after applying to refresh boot link-title settings.

## 2026-11-16 — Minimal Employee creation

Applied Property Setters to dev3; checked metadata and native defaults. Browser verified exactly the four input fields, Company default and hidden Male gender. Server validation accepted an Employee with only the four requested values plus automatic Company/Gender defaults (test transaction rolled back). JavaScript syntax and whitespace checks passed.

Enabled native Employee Quick Entry with Employee Name (stored in first_name), Date of Birth, Status and Date of Joining. Company uses native defaults and is requested only when missing. Gender defaults to Male and is hidden; Salutation is hidden. Existing employee values are preserved. Full-form advanced employment fields and native validation remain available. HER setup installs Property Setters, and a scoped Employee QuickEntry subclass controls only the creation popup.

## 2026-11-16 — Restore standard Item Details visibility

Applied Custom Field placement update and cache clear on dev3. Browser confirmed Item Group, stock UOM, Maintain Stock and Is Fixed Asset are visible; selecting Is Fixed Asset reveals Asset Category. Ordinary Items keep the crane price table hidden. Verified native tab boundaries and whitespace; browser test did not save changes.

Moved the HER Crane Period Prices custom section from after standard_rate to after uoms, at the end of the native Details tab. Its crane-only depends_on previously swallowed the intervening native Item fields into a hidden section for ordinary Items. Item Group, stock UOM, Maintain Stock, Is Fixed Asset and related standard options now retain ERPNext's native visibility and edit rules. No inventory or asset values are changed. Setup updates the Custom Field placement on existing sites and future migrations.

## 2026-11-16 — Crane list render fix

Ownership before_render now passes Crane to frappe.get_list_view, with a missing-instance guard. The previous missing argument resolved no list instance and stopped row rendering. Browser verified all nine Crane rows and segmented/rental ownership bars in Arabic; focused rendering-hook regression and syntax/whitespace checks passed. Existing unrelated null/join startup errors remain observable but do not prevent the list rendering.

## 2026-11-16 — Native rental Location links

Validation: 19 workflow tests passed; one legacy-column test skipped. Added regression for Link metadata, migration idempotency and unchanged rental rows/timestamps. All existing dev3 locations resolve; whitespace checks passed.

Assignment and Timesheet Location fields now link to ERPNext Location. Assignment selection still fills the Timesheet location, and matching requires the same Location record. Migration creates missing native Locations from historical text and changes references only if native naming normalizes the value; submitted work, dates, rates and modification timestamps remain intact. Applied to dev3 and verified every saved rental location resolves. New entries use the native searchable Link control and normal Location permissions.

## 2026-11-16 — Crane list ownership column

Replaced Model in default Crane list columns with Ownership: compact classification and segmented owner-share bar, with owner/percentage tooltip. Supplier-hired cranes show their rental classification and orange bar instead of retained ownership shares. Shares are batch loaded only for permission-visible cranes. Model stays editable in the form. Applied metadata migration on dev3; verified endpoint permissions and list metadata. JavaScript syntax and whitespace checks passed. Browser verification was blocked by a 60-second site navigation timeout.

## 2026-11-16 — Invoice deletion circular-link fix

Sales/Purchase Invoice on_trash clears only its managed Timesheet reverse link for draft/cancelled documents. Invoice cancellation retains historical links using the existing narrow ignore rule. Other native payment, settlement and repair links remain protected. Draft ACC-SINV-2026-00007 backed up privately and deleted at user request; TS-00008 and TS-00009 remain submitted with empty sales_invoice links. Regression verifies draft deletion and regeneration. Workflow suites: 18 passed, one legacy test skipped.

## 2026-11-16 — Supplier rental classification

Hired from Supplier takes precedence over retained owner rows: classification is Hired from Supplier and compatibility type Rented. The form shows the supplier instead of a company share bar and hides the ownership table. Migration corrects existing hired cranes including CR-00009 without deleting ownership rows or dated agreements.

## 2026-11-16 — Editable rental units through sales billing

Applied migration/setup to dev3. Rental workflow and Timesheet suites: 18 tests run, 17 passed, one legacy-column test skipped because those removed columns are absent. Regression coverage verifies editable Timesheet terms, master/explicit default precedence, monthly quantity precision, draft invoice edits, migration preservation and rejection of conflicting same-day flat terms. Browser verified visible Crane default, Assignment-derived Day/1,500, editable Timesheet Month/45,000 surviving refresh/date edits, and the corrected draft invoice rows. JavaScript syntax and whitespace checks passed.

Crane now stores an editable Default Selling UOM, initially filled from HER Settings. Assignment rows inherit the Crane unit and matching reference price; explicit choices remain editable. Timesheets inherit Assignment terms as visible defaults, with editable unit/rate overrides retained on save and used for shift amounts and sales billing. Submitted Timesheet terms are the billing snapshot; changing a master default does not reprice existing work. Sales Invoice lines use the actual Hour/Day/Month quantity and agreed unit rate, with actual crane hours as the stock-UOM conversion and nine-decimal sales quantity precision for monthly fractions. Conflicting flat billing terms for the same booked crane/day are rejected to prevent duplicate charges. Supplier billing remains independent.

Migration fills only missing Crane defaults, preserving historical rentals and invoices. The user's draft ACC-SINV-2026-00007 was backed up and corrected from 1 Hour × 4,500 to 3 Day × 1,500 for CR-00009; its other line and total 9,000 are unchanged.


## 2026-11-16 — Crane ownership share bar

Applied on dev3. Browser verified 50/30/20 segment widths, Arabic classification, safely displayed owner names, live updates, incomplete-total warnings, empty ownership and mobile layout without overflow. Existing form startup null/join errors observed in earlier checks remain outside this presentation change. Syntax and whitespace checks passed.

Replaced the Crane Ownership field’s plain classification and technical description with a segmented owner share bar. Each owner has a colored segment plus a name/percentage legend, using Shareholder titles when permitted. Updates on ownership, owner selection, add/remove and form refresh. Incomplete draft totals show an explicit warning. Classification, validation, ownership/profit calculations and historical agreements remain unchanged; no schema change.


- 2026-11-16: Removed the workspace CSS rule that forced its sidebar hidden. Frappe’s native three-line sidebar toggle now controls navigation visibility and the mobile overlay. Browser verified desktop open/close and mobile overlay open/dismiss with no JavaScript errors.

- 2026-11-16: Highlighted the six frequent workspace destinations (Cranes, Work Log, Servicing, Expense Entries, Sales Invoices and Purchase Invoices) with blue backgrounds, stronger text and an accent border, supporting light/dark themes and both interface languages.

## 2026-11-16 — Shallow regenerated panorama (latest)

Regenerated the crane image with distant vehicles and low booms composed for a shallow panoramic strip. The workspace now uses `cranes-panorama-v2.png`, displayed at 10:1 with a hard maximum height of 25vh/25svh and a focal position of 62%. This supersedes the tall 3:1 banner. Sections/الأقسام remains removed.


## 2026-11-16 — Full crane banner

Increased the crane banner from 10:1 to the image’s native 3:1 ratio and used contain sizing so all three cranes remain visible without cropping. Removed the Sections/الأقسام heading from the template and dev3’s saved workspace. Existing site edits are preserved.


## 2026-11-16 — Requested workspace wording and banner

Renamed Rental Operations in Arabic to «عمليات على الونش», with links ordered «سرك الونش», «صيانة الونش», «تكليف الونش». Removed the separate Maintenance card, Quick Access, overview text, top Customize/Refresh actions and bottom Timesheet/Maintenance reports. Added a generated crane photo displayed at approximately 10:1. Native bottom Edit remains available. Applied to dev3 after a private workspace backup; migration persistence remains unchanged.


## 2026-11-16 — Arabic interface audit

Extended the app Arabic catalog with current workspace, rental, maintenance, asset, settlement, payment and validation text. Added over 300 Arabic entries and tested the workspace, Crane, Assignment, Timesheet, Maintenance and HER Settings in Arabic. All extracted app messages now have Arabic entries apart from six internal naming patterns that must retain their ID format. The browser also confirmed Arabic form descriptions and autocomplete announcements; stored customer/company names remain user data. Frappe and ERPNext use their installed Arabic catalogs. The reference workspace overview and custom actions now translate in Arabic mode. Arabic browser checks showed no English UI words in the workspace; the new Crane form labels also translated. Global Frappe/ERPNext labels use their installed Arabic catalogs. Stored user-entered names, IDs and currency symbols are data and remain as entered. Clear site cache after updating translations.


## 2026-11-16 — Reference-style workspace (latest)

Verified Customize, card Label/Card Links dialog, native Save, All workspaces navigation, desktop/mobile light/dark layouts and no browser errors. All 15 record totals reconcile with permission-filtered queries; Guest access is denied. Saved banner styling and eight cards persist, and repeated setup preserves the layout.

Matched the supplied reference using a compact overview, Quick Access pills, eight native section cards in four desktop columns, colored markers, row icons and permission-filtered counts. Customize invokes native Edit; All workspaces toggles the navigation sidebar. Native card labels, links, order and widths remain editable and persist through migrations. The previous compact layout is backed up on dev3 to `private/backups/her-workspace-before-reference.json`. See [on-site editing instructions](WORKSPACE.md). This supersedes the six-panel arrangement below.


## 2026-11-16 — Compact workspace and slate-blue theme (latest)

Verified native Edit, desktop/mobile light and dark themes with no overflow or browser errors. All workspace sections fit in the 1440×1000 desktop view.

Replaced the large welcome banner and repeated section descriptions with six compact frequent-action tiles, six native link panels (Billing, Treasury, Partners, Reports, Directory, Settings), and two report-builder shortcuts. All 28 destinations remain accessible. The shared theme now uses slate blue, a light navigation rail in light mode, coordinated dark surfaces and flatter controls. This supersedes the yellow/graphite theme and the spacious workspace arrangement below. Native Edit/Save and migration persistence remain in place. Applied the requested revision explicitly to dev3, backing up its prior layout to `private/backups/her-workspace-before-compact.json`; other initialized sites retain their arrangements.


## 2026-11-16 — Editable Crane Operations workspace

Applied on `cranes-dev3.arab-erp.com`. Verified all 28 shortcut destinations, native editor save and persistence through repeated setup. Browser checks passed for Edit, desktop/mobile light and dark layouts, no horizontal overflow and no JavaScript errors. Python compilation and whitespace checks passed. No schema change.

Crane Operations now groups native editable shortcuts into Daily Operations, Billing & Treasury, Partners & Profit Sharing, Reports, and Setup & Directory. Consistent card sizes, section descriptions and an industrial welcome panel support light/dark themes and mobile layouts. Added direct access to purchases, settlements, the distribution dashboard, suppliers and assets.

The layout is installed once from `heavy_equipment_rental/templates/crane_operations.json`. It is a site-owned Workspace (no Module), outside Frappe's standard workspace synchronization; later setup/migrations preserve site edits, including developer-mode edits. The first upgrade saves the complete previous Workspace to the site's private `backups/her-workspace-before-v2.json`. Existing workspace access roles remain unchanged. This supersedes the earlier instruction to retain the old workspace ordering. See [workspace editing](WORKSPACE.md).


- 2026-11-16: Crane Create menu ordered Timesheet, Expense, Maintenance, Sales Invoice, Profit Settlement; existing Payment action follows last. Permissions still control available entries. JavaScript syntax/whitespace checks passed; dev3 cache cleared.

- 2026-11-16: Removed the Crane Change Agreement shortcut. Edit terms and Agreement Effective From directly, then Save; dated history and server validation still apply. JavaScript syntax and whitespace checks passed; dev3 cache cleared.

- 2026-11-16: Maintenance cost is displayed as Amount (EGP), using the native Currency field with EGP formatting.

## 2026-11-16 — Simple repair entry

Applied migration on dev3. All 29 posting/lifecycle/rental tests passed, followed by three focused checks covering Quick Repair, mixed supplier bills and mixed capitalization after final changes. Confirmed native GL expense amounts, full supplier payment, stock-only consumption and cancellation. JavaScript syntax and whitespace checks passed; browser interaction was not exercised.

The Maintenance form now offers Quick Repair (default), Use Stock Parts, and Supplier Bill. Quick Repair uses the HER company repair expense account and payment method, automatically resolving/creating its Expense Entry Type. Supplier Bill accepts stock parts and non-stock labour together; native purchase posting receives parts, and a Material Issue consumes only stock rows. Supplier payment defaults to full and supports partial/zero payment. Advanced Accounting retains capitalization, owner recovery, no-cost work and existing/manual documents. Legacy source values remain stored for compatibility; migration fills presentation choices without reposting or changing financial history. Mixed improvement bills use native Asset Repair service expenses plus stock consumption.

## 2026-11-16 — Maintenance form defaults

New Crane Maintenance records default Actual Start Date and Actual End Date to Today using native Date field defaults. Maintenance Type is removed from default list columns and retained on the form. Existing dates are preserved. Migrated dev3; verified new-document defaults/live metadata and all three rental workflow tests.

## 2026-11-15 — General Ledger rental filters

Crane/CPS GL filters also trace native Payment Entry References for source invoices/journals and settlement journals (complete payment vouchers, including shared payments). CPS-00008 Cash - T movement verified: receipt 3,600 less expenses 490 and partner payment 988.70 = 2,121.30. Select March 2–November 15 to include all four cash movements.

Added Crane and CPS filters to native General Ledger. Live CPS-00008 trace resolves SI-00006 and journals 00014/00015/00016; income minus expenses reconciles to EGP 2,121.30 over March–November 2026. Four GL regression checks and three rental workflow tests passed; JavaScript syntax/whitespace checked; dev3 cache cleared. No schema migration or ledger mutations. Browser UI was not exercised.

- Expense Entry field order is Crane → Crane Timesheet → Crane Assignment.

- Expense Entry rental pickers now send only Posting Date, Crane, Company and an explicitly selected Assignment. No empty From/To filters appear. Work choices must include that one posting date; changing it refreshes/clears invalid selections. Maintenance behavior and submitted allocation snapshots are unchanged. Verified frontend filter arguments/date changes and native search against live Timesheet dates; syntax/whitespace checks passed. No schema change.

- Latest date clarification: Expense Entry uses Posting Date as its single expense date. Its legacy service From/To fields remain stored but hidden and ignored for expense date calculation; assignment/timesheet selection no longer fills a range. Explicit rental links remain authoritative. Maintenance retains Actual Start/End dates and its repair-period behavior. Historical submitted snapshots are preserved. Migrated dev3; date checks confirmed Expense Entry uses Posting Date despite stored legacy ranges and Maintenance retains its range. All three rental workflow tests, JavaScript syntax and whitespace checks passed; fixtures rolled back.

## 2026-11-15 — Expense Entry loading fix

- Removed explicit query suffix from the shared rental_context.js require URL in Expense Entry and Maintenance. Frappe AssetManager.extn interprets a query suffix as the extension, then throws before unfreezing the form. Native asset loading already adds cache versions to fetch URLs.
- Verified both callers with the actual Frappe asset loader: shared script executes and freeze count returns to zero. JavaScript syntax and whitespace checks passed; cleared dev3 cache. No schema changes or accounting changes. Browser interaction was not exercised.

- Crane ownership/profit and operating-fee percentage fields now use one decimal place (100.0).

- Partner links use native Shareholder title display so child tables show partner names while retaining their original linked IDs. Applies to Owners & Profit Shares, Operating Fees and settlement shares. Migrated dev3; native link-title resolution and three rental workflow tests passed. Test records rolled back.

- Crane Operations tab and its shortcut panel removed at the user’s request. The form opens on Details; other tabs retain their order. Migrated dev3; live metadata checks, JavaScript syntax, whitespace checks and three rental workflow tests passed. Test records rolled back.

- Moved ownership_partners directly under the collapsible Owners & Profit Shares section, retaining the other fields in their existing order.

- Crane form: Owners & Profit Shares, Fixed Asset & Ownership Value, and Operating & Distribution Agreement use native collapsible sections, closed initially and expandable by clicking their headings. Field arrangement preserved. Migrated dev3; live metadata checks and three rental workflow tests passed. Native Frappe expands sections with missing required fields so validation remains accessible.

- Mutual-exclusion verification: seven ownership/rental integration tests and JavaScript checks for switching in both directions passed on dev3. Test fixtures rolled back. No schema changes; syntax and whitespace checks passed.

**Latest rule (2026-11-15):** Enable Profit Sharing and Hired from Supplier are mutually exclusive. Selecting either clears the other on the Crane form; server validation rejects both together. Both may remain off for ordinary company work. This supersedes earlier combined-hire/profit-sharing guidance. Existing agreements and posted documents are not rewritten.

## 2026-11-15 — Crane form visibility

- Ownership classification appears only after the Crane is saved. Removed the Agreement Partners section's self-hiding dependency so its Enable Profit Sharing checkbox remains accessible when off. Preserved the user's current field order and clarified the checkbox description. Migrated dev3; live metadata visibility checks and all three rental workflow tests passed. Test records rolled back; whitespace checks passed. Browser interaction was not exercised.


## 2026-11-15 — Operating Fees table (latest)

- Migrated cranes-dev3 successfully. Ten integration tests passed across fee calculations, posted external entitlements, default/invalid rows, dated agreement changes, unchanged submitted snapshots, idempotent migration, ownership, combined supplier hire/sharing and rental workflows. Tests rolled back. Python/JavaScript syntax and whitespace checks passed. Browser interaction was not exercised.

- Crane uses Operating Fees rows: Our Company, Partner (Shareholder), Fee Basis and Operating Fee %. Default is Our Company / Grand Total / 0%. The previous single-recipient fields are hidden and retained for historical agreements.
- Grand Total means crane-allocated invoice revenue before expenses. Net Profit means positive Grand Total minus allocated expenses, before operating fees. Each row uses its own base independently; rates do not compound. Combined percentages cannot exceed 100%; settlement deficit controls still apply. Revenue remaining after fees and expenses follows Owners & Profit Shares.
- Fee rows are versioned with the agreement; settlement snapshots retain each base, rate and amount, and native partner entitlements combine operating fees and remaining-profit shares per recipient. Historical single-operator snapshots keep their original calculation and revenue basis. Migration exposes existing fees without reposting or rewriting history. New table-based agreements use Grand Total revenue for the distribution calculation.


## 2026-11-15 — Simplified crane ownership, operating fees and hire

- Owners & Profit Shares is the ownership source, including a default 100% Company row for new cranes. Ownership classification is calculated. The manual ownership type and new-agreement calculation selector are hidden; historical internal types and dated agreements remain available for compatibility.
- Hired from Supplier is independent of ownership and profit sharing. Supplier rates/units remain on Timesheets; supplier invoices are operating costs before residual profit distribution. Ordinary hire may leave ownership unrecorded.
- Operating Fee % and recipient replace ownership-dependent operator choices. External fee recipients may be any permitted Shareholder in the same Company, including someone outside the owners table. A company-only owner table can pay an external operating fee.
- Migration fills hire flags/classification and missing Company-owned rows without reposting transactions or changing historical agreement snapshots.
- Migrated cranes-dev3 successfully. Seven integration tests passed: default Company ownership, independent supplier hire, repeatable migration/history preservation, external operator outside the owners table with posted entitlement, combined hire/profit sharing with posted supplier invoice, and three rental workflow regressions. Test fixtures rolled back. Python/JavaScript syntax and whitespace checks passed; browser interaction was not exercised.

## 2026-11-15 — Explicit Maintenance / Expense attribution to CPS

- Timesheet CPS costs use the selected rental links only: direct Timesheet first, otherwise all submitted crane Timesheets of the selected Assignment weighted by working hours. Unlinked costs remain general crane expenses and are excluded. Removed date-based link autofill; searches and Maintenance attribution allow earlier work independently of repair/posting date. Forms describe the selected allocation and show Unallocated for empty links.
- Pending repair and expense closure guards follow those same links. Historical captured sources, including an Expense Entry's journal, remain protected even without links. Existing submitted settlements, source links and accounting are unchanged; legacy Period closures continue prorating explicitly linked costs by service days.
- On cranes-dev3: 34 settlement/rental integration tests passed, followed by 6 final checks covering historical unlinked-source protection, shared-cost cancellation, native repair allocation and rental workflows. Tests rolled back; site test settings unchanged. JavaScript handler checks passed for both forms (no date autofill, selected Timesheet fills Assignment, date changes preserve selection, allocation descriptions); Python/JS syntax and whitespace checks passed. No schema change or migration needed.
- Read-only CPS-00004 verification: saved submitted operating expenses remain 700 EGP; fresh calculation excludes its unlinked repairs and gives 0 EGP. No business settlement was cancelled or recalculated in place.

## 2026-11-15 — Native Maintenance lifecycle

- Made Crane Maintenance submittable with native Submit, Cancel and Amend. Submission posts automatic repair documents and cash expenses; cancellation previews related documents and reverses them atomically in dependency order. Amend clears generated links before native validation and permits corrected dates/items/payment amounts. The previous Complete Repair endpoint now delegates to native submission for old open forms.
- Cancellation includes native supplier/customer payments, newest Asset Repairs, stock issues, invoices and cash expenses/journals. Earlier My Stock purchases stay outside scope. Shared payments across unrelated invoices, adjustment reconciliations, closed periods and later repairs remain blocking dependencies; all partial reversals roll back on failure. Submitted jobs reject extra repair documents. Native permissions apply.
- Backed up dev3 database/public/private files (`20261115_131531-cranes-dev3_arab-erp_com-*`), then migrated. Metadata-only patch archives old lifecycle values, marks completed/already-posted jobs submitted and cancelled jobs cancelled, preserving original status/dates/modification time and financial postings. No existing business repair was submitted/cancelled through hooks.
- **32 integration checks passed**: the 31-case posting/lifecycle/rental/manual-repair suite plus the focused newest-first multi-Asset-Repair test after its ordering fix. Covers paid and unpaid repairs, cash journals, changed-date/quantity/payment amendments, stock restoration, payment/permission failure rollback, later-asset blocking, shared-payment isolation, stale preview, forged-link rejection and migration repeatability. Test transactions rolled back.
- Actual headless Chrome verified native Submit → cancellation preview → Cancel → Amend on a temporary No Cost repair, editable Planned amendment and cleared generated links, with zero page JavaScript errors. Removed the temporary repair/crane and revoked its browser session. Syntax and whitespace checks passed.

## 2026-11-15 — One completion flow for repairs and improvements

- Rebuilt automatic completion to support Operating Expense and Capitalize Improvement across My Stock, External Parts and External Service. Complete Repair saves pending edits and creates native purchase/consumption, Asset Repair and supplier payment documents atomically. Improvements consume parts through Asset Repair; purchased parts are not capitalized again as invoice service costs.
- Source and purpose are adjacent; normal automated purpose choices are routine expense or improvement. Accounting defaults stay out of the entry flow. The explicit completion button replaces the direct Completed status option for unposted automatic jobs. Manual Documents remains for historical/other native workflows. Existing business records were not posted or changed.
- Migrated dev3. All **22 integration tests passed**; the three-source capitalization test was rerun successfully after adding the stock-invoice double-capitalization guard. Integration coverage includes all three capital sources, native asset increases/cancellation, duplicate completion and rollback after Asset Repair permission failure, alongside existing payment, stock, rental and manual-repair cases. Node checks cover all six automatic source/purpose combinations, new-form completion action and status/purpose controls. Browser interaction was not exercised.

## 2026-11-15 — Simplified maintenance and supplier payments

- Accounting Treatment now stays visible in Maintenance Details for every source. Automated sources show it read-only, with help explaining that automation supports Operating Expense only; unposted Manual Documents allows other choices. Moved the field outside the hidden Advanced Accounting section. Migrated dev3; all 3 rental workflow tests passed (rolled back), plus Node checks for layout, visibility, editability and help text across all four sources and Planned/Completed/Cancelled states.

- Accounting Treatment now updates its help text when selected and when opening a saved repair, explaining all five treatments. Verified all choices and fallback text with Node; JavaScript syntax/whitespace checks passed. No schema change.

- Added company-specific HER Maintenance Defaults for repair Expense Account, default supplier Payment Method and optional warehouse override. External parts automatically use a Maintenance warehouse; routine repairs hide Advanced Accounting. Replaced empty Repair Source with Manual Documents via an idempotent historical-label patch, preserving financial documents and modification dates.
- Supplier Paid Amount defaults to the full native invoice, supports partial/zero payment and atomically posts a native Payment Entry with purchase, consumption and completion. Connections links the generated supplier payment. Failed payment rolls back all postings; completed historical repairs do not create new payments.
- Migrated cranes-dev3.arab-erp.com. **21 integration tests passed**: 13 automated repair/default/payment cases, 3 rental workflow cases and 5 manual native repair regressions. Covered full/partial/zero/overpayments, rollback after receipt or payment failure, default/overridden warehouse, settings validation, historical-label repeatability and input locking. Tests rolled back without changing site test settings. Node handler checks verified payment defaults, preserved partial amounts, warehouse visibility and Advanced Accounting visibility. Syntax, metadata Connections links and whitespace checks passed; no browser interaction was tested.

## 2026-11-15 — Routine repair posting on Maintenance

- Added Repair Source dropdown, inline item/quantity/warehouse/purchase-rate rows, Supplier invoice details and company repair account/Cost Center. Post Repair & Complete atomically submits Material Issue (own stock), stock-updating Purchase Invoice + Material Issue (external parts), or service Purchase Invoice (external labor). Native valuation and expense-ledger sources prevent double counting.
- Added a native Connections tab for stock/accounting and rental links. Generated links and financial inputs are protected; repeated completion is idempotent, failed posting rolls back, and stock issues must be cancelled before purchased receipts. Blank-source/manual repairs and historical postings remain unchanged; serial/batch/complex purchases retain the native workflow.
- Migrated cranes-dev3.arab-erp.com successfully. **14 integration tests passed**: 6 new automated repair tests, 3 rental workflow tests and 5 existing native repair/accounting regressions. The legacy fixture's hardcoded company was mapped to this development site's Company only during test setup. Tests were rolled back and the site's test configuration was unchanged. Python/JavaScript syntax and diff whitespace checks passed. Browser interaction was not exercised.


## 2026-11-14 — Disposed-asset restrictions and company selection

Implemented asset eligibility checks and company derivation within HER; no schema changes or historical accounting edits. All 32 focused integration/regression tests passed on dev3, including the two previously failing company-selection cases and native scrap/restore booking checks. Test transactions rolled back. Dev server reloaded the Python changes and dev3 cache was cleared; no migration required. Evidence: `RENTAL_GUARDS_TEST_RESULTS_2026-11-14.json`. The earlier audit remains a historical snapshot, not the current implementation status.

## 2026-11-14 — Production readiness audit

- Audited commit `a8a69e4` on dev3 after a database/files backup. Original 145-case integration run: 139 passed, 5 failed, 1 skipped. Five controlled fixture reruns passed; original results remain recorded, and the retired-column migration case still needs an upgraded database.
- Confirmed a scrapped linked Asset still permits a new crane booking. Confirmed Timesheet-first company defaults can create a wrong-company Assignment/invoice draft; the existing submission guard blocks that invoice. Production release is on hold pending these fixes and remaining release checks.
- Native asset acquisition/payment/scrap/restore probes, 1,000 randomized allocation checks, Python/JSON parsing, frontend build and browser page-load smoke checks completed. No unbalanced active GL vouchers or broken submitted expense/settlement journal links found. The saved existing Asset's opening value needs reconciliation before production.
- Rolled back test transactions and temporary company; removed audit browser session. No functional/schema changes. See [full findings and release matrix](PRODUCTION_READINESS_2026-11-14.md), [all executed cases](PRODUCTION_AUDIT_CASES_2026-11-14.md), and [raw evidence](PRODUCTION_AUDIT_RESULTS_2026-11-14.json).

## 2026-11-14 — Cancel button handles linked payments and expenses

- Removed the extra correction/recalculation buttons and their backend workflow. Extended the existing Cancel preview/execution to Expense Entry, affected/later period settlements and submitted native payments. Warn that a combined payment reverses in full and cancellation does not recover actual cash. Permissions, changed-scope confirmation and atomic rollback remain enforced.
- Native settlement Amend now clears the copied generated journal before link validation, recalculates costs on save and updates the Timesheet settlement link on submission. No schema change; cancelled records remain intact.
- All seven targeted cancellation integration tests passed on dev3: paid expense cancellation/native amendments, combined partner payments, customer receipts, changed scope, permission denial/rollback, shared expenses, and existing invoice/Timesheet/settlement cancellation scopes. Migrated dev3 and versioned the script URL; test transactions rolled back. Chrome verified native Cancel previews on EXPE-00001, CPS-00002 and their Sales Invoice, linked payments and reversal warning, no extra buttons and no JavaScript errors. Dismissed confirmations; existing business records remain submitted. Removed the temporary browser session.


## 2026-11-14 — Expense cancellation/amendment fix

- Fixed inherited cancelled Journal Entry links blocking new Expense Entry amendments, within HER's existing controller override. No schema change or migration; historical records unchanged.
- Six expense integration tests passed on dev3, including amendment/new journal and rejection of unrelated journal links. One additional existing test (`test_unrelated_journal_keeps_native_party_validation`) failed because native journal submission did not raise its expected ValidationError; not changed by this fix.
- Rehearsed correcting the saved shared-crane expense from 1,500 to 2,000 and rebuilding its settlement: partner 4,200, company 3,800, original paid Sales Invoice and Timesheet remain submitted. All test changes rolled back.


## 2026-11-14 — New cranes-dev3 development site

- Created `cranes-dev3.arab-erp.com` in the existing bench with Frappe 15.122.0, ERPNext 15.122.0, required `arab_erp_theme` and HER from the current shared workspace. Installation and migration passed; existing sites and unrelated source edits were preserved.
- Verified public HTTPS ping, login page, Administrator authentication, Desk and HER CSS/logo assets. Credentials are stored privately outside the repository; no secrets are recorded here.
- All 49 integration tests passed with zero failures/errors/skips: 3 rental workflow, 23 partner settlement/payment/cancellation, 13 native repair/asset and 10 distribution report/dashboard tests. Ran test cases serially with temporary setup/company/demo fixtures and savepoint isolation; rolled back all fixtures afterward. Confirmed zero Companies, Cranes, Assignments, Timesheets, Sales Invoices and GL Entries remain. Site retains the initial setup wizard for user configuration.


## 2026-11-14 — Open partner entitlements picker and combined payments

- Added “Get Outstanding Partner Entitlements” to draft Pay entries for Shareholder/Supplier, with Arabic labels, a selectable balance table and posting-date/Crane/Timesheet/invoice filters. Restrict results to the selected party, Company and payable account with source read permissions; append native journal references without duplicates.
- Extended Shareholder partial allocation to multiple settlement journals and validated every contributing settlement. Combined payments clear misleading single-source header links; native journal references and payment ledgers drive each settlement's balances/status. Existing entered amounts remain editable; empty payment amounts default to selected outstanding totals.
- All 23 partner integration tests passed, including multi-invoice selection/filtering, party isolation, fully paid exclusion, partial allocation, native posting/cancellation, per-settlement reports and permission/account checks. Browser verified three live open entitlements, duplicate prevention, 1,000 allocated as 920 + 80, and successful combined draft save with no single-settlement header or JavaScript errors. Verification draft removed; no live payment submitted. Python/JavaScript syntax and whitespace checks passed; no schema migration needed.

## 2026-11-14 — Arabic entitlements and partnership dashboard

- Added native Desk page `crane-distribution-dashboard`, workspace shortcut and report button. Arabic RTL filters, financial cards, clickable status bars, five detail views, document links, table search/pagination and native report export handoff. Responsive layout, keyboard focus and reduced-motion support.
- Reuses the comprehensive report calculations in one request and its report-role/source permissions. Counts partner entitlements once per settlement; posted cards and draft estimates stay separate. Company-context versus partner-filter totals are explained on the page. No accounting writes or schema changes.
- Synced Page and Workspace on cranes-dev2.arab-erp.com. All 10 report/dashboard integration tests passed, including exact report reconciliation, partner/status filtering and denied report access. Browser verified all five views, clickable status filtering/reset, search and 390px/1450px layouts without JavaScript errors or page overflow on the local development server.

## 2026-11-14 — Fix partial partner payments from Desk

- Reproduced from CPS-00017 → Partner Payment: changing Paid Amount from 920 to 300 reset its Journal Entry allocation to zero, then save failed with “The payment must reference its submitted settlement Journal Entry.” The native allocator omitted Shareholder from its positive Pay branch.
- Added a scoped Payment Entry allocator for the single Shareholder journal reference created by the settlement action. Preserve the allocation toggle, deductions, outstanding cap and native save/submit validation; unrelated payments retain the native method. Fixed the button's jQuery/native Promise mismatch as well.
- All 21 partner settlement integration tests passed, including the actual form allocation method, partial posting, remainder payment, cancellation/restored balances and native delegation. Browser retest on the local development server preserved the 300 allocation, zero difference and successfully saved the draft. External URL returned 502 during verification. No schema migration or historical ledger changes; test transactions rolled back.

## 2026-11-13 — Comprehensive Crane Profit Distribution report

- Added native Script Report **Crane Profit Distribution** with five views: settlement summary, participant summary, detailed distribution, source revenue/costs and entitlement/payment movements. Shows Company operating/residual/total retention, separate ownership/profit percentages, each party's rounded expense burden, posted/pending entitlements, Payment Entry payments, other adjustments and outstanding balances. Participant totals aggregate across settlements; cards count each selected settlement once and posted/draft totals stay separate.
- Added Company, work/posting date basis, period, Balance As Of, Crane, Shareholder, customer, Assignment, Timesheet, settlement, invoice, posting/payment status and participant filters. Use saved snapshots and native payment-ledger movements; no report recalculation/posting. Read-check every contributing source/party/payment; whole overlapping settlements are selected without date proration. Native Excel/CSV/print remain available.
- Added workspace shortcut, Crane hub action, settlement View action and Arabic translations. Documented filter semantics, draft estimates, current-ledger cancellation behavior, Company retention versus cash, and the actual CR-00074 reconciliation in [the Arabic report guide](PROFIT_DISTRIBUTION_REPORT.md).
- Backed up (`20261113_215924`) and migrated cranes-dev2.arab-erp.com. Accounting document/ledger counts were unchanged by migration. All 9 targeted report tests and 3 rental workflow tests passed; the 17 existing partner/accounting tests also passed during the regression run. Covered shared invoices, independent profit/ownership, one-cent rounding, source expense-type splits, partial/future/cancelled payments, non-cash adjustments, posted/draft separation, snapshot immutability, date/document/partner/status filters and denied-source permissions.
- Live browser verified all five views, bookmarked Link filters, native Excel export, desktop/mobile and no page errors/overflow. Wait for Link validation before the first report query; use summary cards and native tables to keep rapid view/viewport switches stable. Confirmed CPS-00023: revenue 48,000; costs 50; Company 4,800 operating + 17,260 residual = 22,060; external entitlements/payments 25,890; outstanding zero at verification. Temporary browser authentication removed. Python/JavaScript/JSON/whitespace checks passed.

## 2026-11-13 — Isolate demo revenue accounts from shared rental defaults

- Investigated submitted ACC-SINV-2026-00033 for CR-00074: it inherited HER1313 Rental Revenue - CC from HER-RENTAL-SERVICE's company Item Default. ERPNext SellingController fills an empty Item income-account default from a non-company invoice-row account even when saving a draft; the earlier 1313 demo triggered this.
- Backed up the shared Item and invoice GL privately, restored the shared company Item default to Sales - CC through normal Item save/history, and verified native item-detail defaults for subsequent invoices. Existing submitted invoice 00033 and GL remain unchanged.
- Both development demo scripts now preserve/restore shared rental Item income-account defaults around creation. Two integration tests passed, exercising a real draft invoice's native default-learning side effect, the next invoice's company fallback, and restoration after failure. Syntax and whitespace checks passed.

## 2026-11-13 — Restore automatic source-revenue settlements and post an existing-Crane example

- Reviewed commit `550f4f5d` and selectively restored pre-redesign settlement defaults: automatic on invoice submission, source-revenue debits, Invoice Grand Total and no depreciation deduction. Hid alternative selectors; Legacy Profit Allocation Account remains only for Legacy Net Profit. Historical alternative terms retain backend compatibility. Assets, stock, repairs and Connections remain supported.
- Backed up (`20261113_210545`) and migrated cranes-dev2.arab-erp.com. The idempotent patch appends dated restored terms after previous versions and submitted periods. CR-00073's restored agreement starts 2026-11-13. Exact comparisons preserved all 477 previous GL rows, 12 Payment Entries, 10 settlements and previous agreement versions before the new example; old posted records remain identical afterward too.
- Live browser verified the restored settings, hidden allocation/alternative fields, automatic submitted CPS-00022, paid-partner table and Connections containing all 11 related Payment Entries. Mobile had no horizontal overflow or JavaScript errors. Temporary verification authentication was removed; the site’s disabled test setting stayed unchanged. Syntax, DocType field-order and whitespace checks passed.
- All 62 integration tests passed: 17 automatic partner/accounting, 29 settlement, 13 native repair/accounting and 3 rental workflow. Covered restored defaults, source Income debits, partial payments, permission rollback, dated/idempotent migration and preserved historical snapshots. The rental workflow suite passed after a serial rerun of a naming-series lock timeout during overlapping test runs.
- Rehearsed with rollback, then posted the explicitly requested example on existing CR-00073. Invoice ACC-SINV-2026-00032 automatically submits CPS-00022 and posts ACC-JV-2026-00245: debit source Income 4,500; credit three Shareholders 1,500 each. Revenue 10,000, operating fee 1,000, costs 1,500, residual 7,500 and Company retention 4,000. Recorded customer receipt and four partner Pay entries, including a 500/1,000 partial-payment sequence. All outstanding balances are zero; eight vouchers balance; repeat execution adds no duplicates. Prior CPS-00021 remains unchanged. See [Arabic example](RESTORED_SETTLEMENT_AR.md) and [results](RESTORED_SETTLEMENT_RESULT.json).

## 2026-11-13 — Include indirect Crane payments

- Corrected the direct-only connections scope: include payments through Asset acquisition and source invoice/journal references, plus invoices/journals attributed to the selected company leaf Cost Center when it is not shared by another Crane. Include expense and depreciation journals. Every hop respects read permissions; unrelated parties/items and shared centers do not expand the results.
- Verified CR-00073 now returns all six Payment Entries (00033–00038), both Purchase Invoices (00006–00007) and all six Journal Entries (00238–00243). Added regressions for indirect payments, duplicate references, reference DocType matching, denied intermediate permissions, shared centers and company boundaries. No posted records changed.

## 2026-11-13 — Crane Connections error and missing links

- Fixed the invalid one-element Asset link definition and replaced the reversed Assignment lookup. Added metadata-driven native connections for all direct Crane references, including accounting dimensions, child-row invoices/journals, payments and outgoing master/owner links. Counts and list routes use the same deduplicated, permission-filtered record names.
- Verified CR-00073 connections against the development database. Four regression tests cover scalar/empty links, Assignment child rows, invoice header/row unions, duplicate suppression and permissions; the three rental workflow tests also passed. Refreshed the development site cache. No schema migration or historical document changes.

## 2026-11-13 — Posted Crane 1313 end-to-end example

- On the user's explicit request, created ونش ١٣١٣ (`CR-00073`) on cranes-dev2.arab-erp.com under cranes company / EGP. Company owns 40% with native Asset cost 300,000 (physical reference 750,000); three external Shareholders each own/receive 20%. Company operating fee is 10% and residual split is 40/20/20/20.
- Posted isolated demo funding, native fixed-asset purchase/payment and depreciation schedule, a two-day rental/invoice/customer receipt, stock purchase/payment and repair consumption, fuel/employee/transport expenses, reviewed entitlement journal and three native partner payments. No taxes in this illustrative example. Only Company-owned Asset value was recorded.
- Rehearsed with rollback before posting; verified 16 balanced native vouchers, cost 300,000 / book value 295,000, Company cash 40,000 and net accounting result 35,000. Each partner received 15,000 and all invoice/partner outstanding balances and parts stock are zero. Repeated execution verified the same IDs with unchanged document/ledger counts.
- Company depreciation is excluded from the shared distribution pool, so contractual Company retention is 40,000 before its own 5,000 depreciation. Report scope differences are documented: Crane rental margin 80,000 before partner expense; Assignment-filtered margin 85,000 also excludes unallocated depreciation. See [Arabic results and comments](DEMO_1313_AR.md) and [reconciliation data](DEMO_1313_RESULT.json). Backup prefix 20261113_201807. The demo is explicit, development-only and never an install/migration hook.

## 2026-11-13 — Track Company assets only

- Replaced manual recognition options with a read-only basis derived from ownership: Owned → Company Owned; positive shared Company interest → Company Interest Only; zero ownership/Rented/Operated for Owner → no Asset link or create action. Removed other-owner Asset allocations; ownership_partners and profit agreements remain unchanged.
- Added a permission-checked company-Asset draft action. Native amounts represent the Company's recognized cost and are not multiplied again or silently rescaled on ownership changes. Company-owned improvements remain supported; zero ownership cannot capitalize through this workflow.
- Backed up the development database (`20261113_190410`) and migrated cranes-dev2.arab-erp.com. The idempotent patch archives obsolete custody/zero-interest and whole-crane partial-interest links without changing native Assets, ledgers or historical agreements.
- All 29 targeted integration tests passed (13 Crane/Asset, 13 native accounting/repair, 3 rental workflow), including derived Owned/shared basis, zero ownership, date-effective shares, unchanged native amounts and migration repeatability. Browser checks confirmed only Company Owned / Company Interest Only remain, the field is read-only, Owned defaults correctly, and desktop/mobile forms have no JavaScript errors or horizontal overflow. Syntax and whitespace checks passed; temporary browser authentication removed. Updated the short Arabic Asset explanation and current guides.

## 2026-11-13 — Short Arabic Asset guide

- Added [ASSETS_AR.md](ASSETS_AR.md): concise explanation of shared-asset logic: one Asset, dated ownership agreements, whole/company-interest recognition, depreciation/repairs, and separate profit, funding and payment amounts. Revised on user request to explain behavior rather than operating steps. Linked from README; documentation only.

## 2026-11-13 — Illustrated user guide

- Added [USER_GUIDE.md](USER_GUIDE.md) with setup instructions, current screen/button names, rental and repair workflows, five Mermaid diagrams, worked ownership/settlement/payment examples, reports, corrections and current accounting/version limits. Linked it from README. Documentation only; no schema or accounting changes.

## 2026-11-13 — Crane-centered native accounting redesign

- Added Crane → Operations as the main hub and moved Cranes to the first workspace shortcut. Start bookings, Timesheets, repairs, Asset/funding work and owner review from the Crane. New cranes reuse `HER-RENTAL-SERVICE`; legacy Item links/mirrors remain intact. Shared-item invoice attribution separates multiple cranes correctly.
- Added reviewed Whole Crane / Company Interest Only / Third-party Custody recognition. User confirmed varying contracts. Native Assets retain acquisition, improvement, depreciation and disposal accounting; no automatic ownership valuation postings, capital contributions or balance rescaling. Company-interest values are not multiplied by ownership percentages again.
- Extended existing maintenance with native operating stock issues/service invoices, justified Asset Repair improvements, separately recoverable owner Sales Invoices and No Cost. Kept Cash Expense for existing/direct-paid repairs. Capitalization uses actual stock ledger values, including serialized parts, and reverses stock and Asset value together. Native depreciation schedules regenerate; company-owned/shared and third-party repair cases are covered.
- New dated agreements use reviewed posting, net revenue and explicit partner Expense/agency revenue/Equity treatment, with posted-depreciation policy. Draft review deficits do not block customer invoicing; deficits and unfinished relevant operating repairs block entitlement submission. Native costs allocate by rental work and are counted once. Owner recovery invoices, stock acquisition, Asset disposal and balance-sheet funding stay outside rental profit; funding remains possible after settlement closure. Existing contracts and submitted snapshots retain historical behavior.
- Added repair stock/service costs and attributed depreciation/journals to Rental Profitability. Native partner journals, partial payments, reports, company/account permissions, dated terms, source/allocation locks and legacy automatic settlements remain supported.
- Backed up and migrated `cranes-dev2.arab-erp.com` (database backup prefix `20261113_170509`). **90 distinct integration tests passed**: the 87-test main run plus native depreciation-schedule, two-crane/shared-item and serialized-part cases. The final 19-test run passed after the last accounting-lock changes and migration. Covered real GL/stock posting, capitalization/cancellation, VAT exclusion, depreciation deduction, owner recovery, funding, permissions, historical settings and migration repeatability.
- Compared pre-change backup/current document counts: GL 436, stock ledger 2, Sales Invoices 9, Purchase Invoices 1, Journal Entries 195, Payment Entries 6, Assets 2, settlements 9 — all unchanged. Test data rolled back; `allow_tests` remains false. No real Asset, stock movement or entitlement was created by migration.
- Live browser checks passed at desktop and 390px: 11 hub actions, correct Crane/Company repair defaults, owner-billing controls, no horizontal overflow and no JavaScript errors. Removed temporary verification authentication. Python/JavaScript syntax, DocType field orders and whitespace checks passed. See [full workflow, accounting decisions and version boundaries](NATIVE_CRANE_WORKFLOW.md).

## 2026-11-13 — Crane Asset links and shared ownership values

- Added one unique, non-copied native Asset link per physical Crane, with native Connections and a live financial panel. The user chose whole crane cost in company books. Reference owner amounts use today's saved ownership percentages, independently of profit distributions/future agreements, and conserve currency totals. Read current depreciation values from the company default Finance Book; missing/ambiguous book values stay unavailable.
- Restricted link changes to Accounts Manager/System Manager with Asset read permission for new selections. Crane's native Version history audits corrections without reversing valid Asset postings. Validate company, single-unit quantity, separate fixed-asset/service Items and explicit third-party ownership for rented/owner-operated cranes; enforce consistency on native Asset edits as well. Preserve cancelled/disposed references and show status; reject new disposed links. Financial display retains native source permissions.
- Migrated `cranes-dev2.arab-erp.com`; verified the unique database index and Accounts Manager permissions. Added no Assets, guessed values, contributions, openings or journals. Existing Cranes remain unlinked until explicitly reviewed. Depreciation/funding stay in native accounting; the link does not change settlement calculations or recognize partner liabilities.
- All **58 integration tests passed**: 10 Crane/Asset, 3 rental workflow, 29 settlement/accounting and 16 automatic partner/context tests. Covered native depreciation posting/reversal, multiple/default Finance Books, whole-cost ownership allocation, audited corrections, duplicates, native Asset edits, permissions and preserved settlement behavior. JavaScript panel checks covered rendering/escaping, unsaved edits, missing book values, permissions and stale responses; syntax/whitespace checks passed. Test records rolled back and the site's disabled test setting remained unchanged.

## 2026-11-13 — Owned Crane checkbox visibility

- Hide Enable Profit Sharing for Owned cranes, retaining its existing Rented exclusion. No saved flag, agreement or accounting changes. Migrated `cranes-dev2.arab-erp.com`; verified visibility for all Ownership Types and passed all 3 rental workflow tests plus whitespace checks. Restored the disabled test setting.

## 2026-11-13 — Optional start-date rental defaults

- Confirmed scope: Crane Maintenance and Expense Entry. Assignment and Timesheet are optional editable links; removed all client/server mandatory-selection rules. Crane plus Actual Start Date (maintenance) or Posting Date (expense) defaults unique matches, without using the end date for discovery. Multiple matching Timesheets are not selected arbitrarily. Users may override or clear suggestions; refresh preserves those choices, with defaults initialized once on new prefilled forms.
- Kept explicit-link consistency validation, permissions and posted-accounting locks. Passed all 16 automatic settlement/context tests; reran the two affected cases after enabling optional maintenance links. JavaScript checks covered both forms, ambiguity, manual clearing, pending edits and initial defaults. Syntax/whitespace checks passed; restored the disabled test setting. No schema migration was needed.

## 2026-11-13 — Inline required rental links; removed maintenance planning dates

- Removed planned date fields and active calendar/query references. A repeatable post-sync patch archives historical planned dates in hidden Legacy Planned Dates without changing actual work dates or record timestamps. Maintenance matching now uses Actual Start/End only.
- Replaced the shared dialog/button with direct editable Assignment/Timesheet Link fields. Native searches filter rental work and show conditional mandatory markers; server validation requires matching Assignment and, when available, matching Timesheet. Expense Assignment searches allow earlier work for late postings. Timesheet selection fills Assignment/read-only service dates. Preserved unchanged historical records and crane-only cases without matches.
- Migrated `cranes-dev2.arab-erp.com`; verified removed fields and archive repeatability. All 3 rental workflow and 16 automatic settlement/context tests passed, including the new required-Timesheet case. JavaScript checks verified editable links, requirements, defaults and no-match fallback; syntax and whitespace checks passed. Restored the disabled test setting.

## 2026-11-13 — Shared rental-work selector

- Maintenance and Expense Entry now share Choose Rental Work: choose Crane/work dates and explicitly select an overlapping Assignment or non-cancelled Timesheet when work matches. Allow Crane-only records when nothing matches. Timesheet selection fills Assignment; the managed link fields prevent conflicting form edits. Expense matching defaults to Posting Date and supports choosing earlier work dates without making service dates editable.
- Added maintenance Assignment/Timesheet links and an expense Timesheet link. Completing maintenance carries its links and actual work period (clipped to selected work) into the native expense; locks linked financial attribution after creation. Timesheet-linked costs allocate only to that Timesheet, with existing source/period/ledger safeguards. Native Assignment and Timesheet Connections expose linked maintenance/expenses. Historical unchanged records and posted sources are preserved.
- Migrated `cranes-dev2.arab-erp.com`; verified live candidates, fields and dashboard mappings. Passed 48 distinct integration tests (3 rental workflow, 16 automatic settlement/context, 29 accounting/settlement), including mandatory selection, crane-only fallback, direct Timesheet allocation and maintenance expense propagation/locks. Final targeted cases passed after date/locking refinements. JavaScript selector behavior, syntax and whitespace checks passed; restored the disabled test setting.

## 2026-11-13 — Assigned Cranes within Assignment Details

- Removed the separate Assigned Cranes tab; the table now occupies a full-width section in Assignment Details. Connections and existing table records/behavior are preserved.
- Migrated `cranes-dev2.arab-erp.com`; verified field/tab order and passed all 3 rental workflow tests and whitespace checks. Restored the disabled test setting.

## 2026-11-13 — Assignment Connections tab

- Added the native Connections tab/dashboard to Crane Assignment for assigned Cranes, Customer, Crane Timesheets and Expense Entries, with correct internal/Assignment field mappings. Invoice/settlement connections remain on their source Timesheet.
- Migrated `cranes-dev2.arab-erp.com`; verified native counts on ASG-00081 (one Crane, Customer, Timesheet and Expense). All 3 rental workflow tests passed, plus Python syntax and whitespace checks. Restored the disabled test setting.

## 2026-11-13 — Read-only expense service dates

- Made Service From Date and Service To Date read-only through HER field setup, preserving automatic Assignment defaults, saved dates and allocation rules. Migrated `cranes-dev2.arab-erp.com` and verified both field definitions. All 3 rental workflow tests passed; restored the disabled test setting.

## 2026-11-12 — Expense Crane filtering and inline rows

- Expense Entry now restricts Crane search to the selected Assignment’s active bookings, respects source/Crane permissions, and clears incompatible selections on Assignment changes. Enabled inline expense Type/Amount entry with HER-owned Property Setters on the shared child grid; retained automatic Account lookup.
- Migrated `cranes-dev2.arab-erp.com`; all 3 rental workflow tests passed. Verified Crane filtering, text search, permission rejection, and migrated editable-grid/column metadata. JavaScript/Python syntax and whitespace checks passed; restored the disabled test setting.

## 2026-11-12 — Editable Driver in Timesheet Entries

- Replaced the read-only Driver Name grid column with the editable Driver (Employee) Link. Kept the fetched name hidden for summaries/history. Verified Driver, Work Date, Start/End Time, Worked Hours, Overtime and Ends Next Day are editable inputs on draft rows.
- Migrated `cranes-dev2.arab-erp.com`; the 3 rental workflow tests passed. Verified migrated field metadata and whitespace checks. Restored the disabled test setting.

## 2026-11-12 — Editable operating hours

- Unlocked Timesheet Entry Worked Hours. Entered values, including zero, survive saves and clock-time edits; driver summaries, hourly sales/purchases and line amounts use entered operating hours. Preserved overlap deduplication, booking checks and historical values. Zero-hour rows are excluded from billable work dates.
- Migrated `cranes-dev2.arab-erp.com`; all 3 rental workflow and 14 purchasing/defaults tests passed. Regression checks cover zero downtime, entered 2 hours surviving a 6-hour clock window, and a 2-hour Sales Invoice. Python/JavaScript syntax and whitespace checks passed; restored the disabled test setting.

## 2026-11-12 — Rental terms in Timesheet Entries

- Added visible Rental Rate and Rental Rate Unit columns to Timesheet Entries, using the matching Assignment crane booking. Draft forms populate them on row/date/Assignment/Crane changes; the controller enforces them when saving or submitting. Retained the previous hourly field internally, existing billing calculations and submitted history.
- Migrated `cranes-dev2.arab-erp.com`; all 3 rental workflow tests passed with entry-rate/unit assertions for Hour, Day and Month. JavaScript behavior checks passed for booking/date defaults and submitted-history protection; syntax and whitespace checks passed. Restored the disabled test setting.

## 2026-11-12 — Assignment rates and Timesheet crane chooser

- Assigned Crane grid now displays Rental Rate and Rental Rate Unit alongside Crane and booking dates. New rows default to Settings Default Selling UOM and the matching Crane reference price in the form and on server save. Removed Frappe's implicit first-option Hour default; retain editable overrides, protect pending/stale responses, and leave saved agreement terms unchanged when settings/prices change.
- Create → New Timesheet prompts for one of the Assignment's distinct active cranes when several are booked; a single crane is preselected directly. Require saving Assignment edits first and exclude cancelled bookings. New Timesheets now default editable period dates plus Rental Rate/Unit from the chosen booking, with a rental-period chooser for multiple bookings of the same crane. Verified single/multiple-crane and multiple-period defaults with JavaScript behavior checks; no schema change was needed.
- Migrated `cranes-dev2.arab-erp.com`. All 3 rental workflow tests passed, including Day defaults, Month reference pricing and preservation after Settings changes. JavaScript behavior checks passed for defaults, manual/pending edits, crane selection and single-crane creation; syntax and whitespace checks passed. Restored the site's disabled test setting.

## 2026-11-12 — Rental expense attribution by work period

- Added Service From/To Date on Expense Entry, Assignment booking defaults, single-crane inference, paired/ordered date and company/Crane/booking validation. Accounting Posting Date remains independent. Expense forms prefill the work dates while preserving manual edits during pending requests.
- Automatic settlements now select posted expenses by Crane, optional Assignment and overlapping service period; shared expenses allocate once by submitted crane hours with captured candidates/weights. Period settlements prorate by calendar days with fixed-date currency rounding and nonoverlapping allocation slices. Excluded linked expense journals from separate source totals. New expense journals carry Crane on both sides, with existing employee attribution preserved.
- Closed service-period costs and captured work allocations require reopening the affected settlements before changes. Existing submitted settlements/ledgers were preserved. Migrated `cranes-dev2.arab-erp.com`; verified EXPE-00118 resolves to 250 EGP for CR-00070 / ASG-00081, 1–3 November despite its 12 November posting. Submitted CPS-00013 retains its original zero expenses and needs cancellation/amendment to apply this cost.
- Passed 50 distinct integration tests: 14 automatic settlement/expense allocation tests, 29 settlement/accounting tests, 2 rental workflow tests and 5 employee-expense tests. The last suite used a temporary missing Employee fixture inside its rolled-back transaction. Covered late postings, Assignment/date isolation, shared allocations, closure guards, period rounding/proration, permissions and historical preservation. JavaScript default/manual-edit checks, syntax and whitespace checks passed; restored the site's disabled test setting.

## 2026-11-12 — External partners only under Operated for Owner

- Operated for Owner now keeps every partner row's Our Company flag unchecked and disabled in the form, including when opening an older form or changing the type. New owner-operated agreements default to an external owner. Server validation rejects company rows regardless of ownership percentage and no longer converts the type to Shared Ownership. Company operating fees continue to appear separately in settlement results.
- Preserved agreement snapshots, posted settlements, percentages and normal effective-date controls. No schema or bulk data migration was needed. Cleared cache on `cranes-dev2.arab-erp.com`.
- Passed all 29 settlement/accounting tests and 2 rental workflow tests (31 total). Form behavior checks cover external defaults, clearing/rejecting company flags, disabled checkbox, preserved ownership type and Shared Ownership allowing company partners. Python/JavaScript syntax and whitespace checks passed; restored the site's disabled test setting.

## 2026-11-12 — Owner profit-share validation

- Crane partner rows now default matching Remaining Balance % values as ownership changes, preserving manually different profit splits. New or changed agreements block positive ownership with zero remaining-profit entitlement unless the row explicitly confirms it. The confirmation is captured in the dated agreement; percentage totals and existing agreement-date/permission controls still apply.
- Added the confirmation checkbox/help text and migrated `cranes-dev2.arab-erp.com`. Verified the current accidental zero-share setup is blocked when changing terms, while unchanged historical agreements remain saveable. CPS-00010 and all its submitted amounts/snapshots remain unchanged; no corrective journal or payment was posted.
- Passed 39 distinct integration tests: 28 settlement/accounting tests (including new rejection/confirmation and 1,080 EGP payable regressions), 9 automatic settlement/payment/report tests and 2 rental workflow tests. Intentional zero-share fixtures explicitly confirm their terms; three affected cases passed on rerun. Form behavior checks cover 60/40 defaults, custom splits, confirmed zero shares and clearing stale confirmations. Python/JavaScript syntax, JSON field order and whitespace checks passed; the site's disabled test setting was restored.

## 2026-11-12 — Removed invoice driver-payment workflow

- Removed invoice operator rows, direct-payment checkbox/journal link, proportional driver shares, customer-to-driver journal action/API and hooks, the Crane Invoice Driver DocType, and driver-payment Settings accounts. Timesheet driver/hour tracking and employee expense attribution remain available.
- Migrated `cranes-dev2.arab-erp.com`. The pre-model-sync patch archived two historical invoices' retired details in hidden read-only JSON, with Settings accounts archived when configured. No invoice amounts, submitted journals or ledger postings were changed. Verified removed metadata and repeat execution preserving the archives.
- Passed both rental workflow tests and all nine automatic partner-settlement/report tests (11 total), plus Python syntax and whitespace checks. Restored the site's disabled test setting.

As of 2026-11-03:

- Simplified Assignment/Timesheet entry, removed the custom `Crane Project` DocType, and migrated historical links while leaving native ERPNext `Project` intact.
- Removed duplicate rental date entry on Timesheets; a new Assignment uses the Timesheet period. Added optional default driver, per-row driver overrides, hard-copy attachment, native Connections dashboard, and a calculated Hours by Driver table.
- Backfill patches preserve earlier signed uploads and populate driver names/hour summaries on existing Timesheets. The local development site `cranes-dev2.arab-erp.com` was migrated and the rental workflow test passed after these changes.
- Updated the Crane form with image, license plate, simplified pricing, today's availability, and native Connections. Added a patch to preserve previous Year prices in a hidden legacy field.
- Migrated `cranes-dev2.arab-erp.com` and passed the rental workflow test after the Crane changes.
- Moved Crane image controls to the side panel, defaulted uploads to public, added a public-image migration, synced reference prices to a read-only Item table, and replaced Availability with a compact monthly reservation view hidden on new Cranes.
- Migrated `cranes-dev2.arab-erp.com` and passed the rental workflow test for the Item price sync and public image requirement.
- Added a photo thumbnail column to the regular Crane List view without changing side-panel image upload.
- Synced the Crane image to the linked Item's native image field and added a backfill patch for existing Items.
- Fixed Crane DocType field arrangement validation by moving the list thumbnail flag from `Attach Image` to a mirrored hidden Data field; existing thumbnail URLs are backfilled.
- Added Create actions on saved Cranes for Expense, Maintenance, Timesheet, and Sales Invoice. The invoice action groups submitted, unbilled work by Assignment.
- The rental workflow test passed with two new draft invoices across two Assignments and no duplicate invoices on retry.
- Removed rental-owned logo and theme assets/hooks and declared `arab_erp_theme` as a required app. Migrated historical Expense Types and Expense Entry amounts to the shared models, linked maintenance to shared types, and handed prior site branding to the base theme. Migrated `cranes-dev2.arab-erp.com`; both rental workflow tests, including completed maintenance expense posting, passed.
- Added an optional Crane Assignment link to the shared Expense Entry alongside the existing optional Crane link. A saved Crane Assignment now offers Create → Expense with its Assignment prefilled.
- Enabled title display for the shared Expense Entry Type links so Expense Entry expense rows show the type name instead of its ID.
- Added HER-owned industrial light/dark styling for Desk, login, calendar, and timeline, using machinery yellow, graphite, and steel gray. Integrated the supplied crane PNG as logo/favicon and GIF into native splash/blocking loaders plus the calendar refresh indicator, with a static reduced-motion fallback. All changes live in this app; no changes to `arab_erp_theme` or Frappe/ERPNext source.
- Built HER assets with `bench build --app heavy_equipment_rental` and the calendar frontend with `npm run build`; applied presentation-only branding on `cranes-dev2.arab-erp.com` without migration or rental setup. Browser checks passed for both themes, login system-theme changes, 320px/390px layouts, RTL form presentation, lists, a native report table, link suggestions, dialogs, nested loaders, startup splash dismissal, reduced motion, and child-row editor backdrops. Fixed narrow timeline toolbar overflow. Snapshot comparisons confirmed all 23 workspaces and their child records, DocTypes, Custom Fields, and Custom DocPerm records remained unchanged. Python/JavaScript syntax and whitespace checks passed. No rental workflow or schema changes were made.

- Set the supplied yellow mobile crane PNG as the main Desk/login/app logo under a distinct `mobile-crane-logo.png` URL so browsers request the correct image instead of reusing the earlier logo URL.

- Refined native form tabs to share a continuous bar background in both themes, removing the alternating white blocks. Active tabs use a consistent yellow underline; hover and keyboard focus keep the shared surface intact.

- Added Supplier to rented Cranes and a conditional Supplier Purchase section on Timesheets with Hour/Day/Month, quantity, and price per unit for the existing service period. Submitting creates and submits a native Purchase Invoice for the linked Crane Item, using the Assignment company currency and normal accounting permissions. Historical submitted work is not retroactively invoiced.
- Added Create → Payment on saved Cranes and submitted, invoiced Timesheets. It opens a draft native supplier Payment Entry against an unpaid submitted invoice, offering invoice selection when needed. Added Purchase Invoice to Timesheet Connections, protected invoice links, and invoice-first cancellation while preserving the historical reference.
- Migrated `cranes-dev2.arab-erp.com`. All four purchasing integration tests and both existing rental workflow tests passed, covering unit pricing, submitted invoices/GL entries, duplicate prevention, payment creation/posting, paid-invoice exclusion, cancellation/amendment, and accounting permissions. Browser checks passed for conditional Supplier/purchase fields, required terms, payment helper loading, desktop/mobile form widths, and no JavaScript errors. Python/JavaScript syntax and whitespace checks passed. Restored the site's original disabled test setting after verification.

- Earlier purchasing design (superseded by the worked-hour change below): replaced manual purchase quantity/unit entry with the Timesheet's inclusive supplier rental interval and existing Billing Unit. Purchase Invoices now show their real Hour/Day/Month UOM, calculated quantity, and entered purchase rate: 13–16 October is 4 Day or 96 Hour; monthly hires use calendar-month fractions. Linked Assignment terms are visible read-only, and the full supplier hire interval must fit its booked crane period. Overlapping purchased intervals are rejected.
- Added an idempotent migration to archive retired manual purchase terms without repricing existing invoices. Setup ensures rental UOMs exist and configures native Purchase Invoice quantity/conversion precision for monthly proration. Monetary Timesheet calculations use currency precision; submitted attachment edits preserve stored totals.
- Migrated `cranes-dev2.arab-erp.com`; all seven purchasing tests and both existing rental workflow tests passed. Coverage includes real invoice UOM/quantity/rate, inclusive rental dates independent of shifts, whole/partial months, hired-hour conversions, overlap/boundary checks, legacy archives, payments, cancellation/amendment, and permissions. Browser checks passed for removed purchase fields, visible/read-only Assignment Billing Unit, supplier fields, invoice quantity precision, and desktop/mobile form widths with no JavaScript errors. Python/JavaScript syntax and whitespace checks passed; restored the site's original disabled test setting.

- Added employee attribution to expense Journal Entry debit rows using the linked Expense Entry's Crane Driver. Native ledger expense rows retain no party, preserving ERPNext's account-party validation, posting, and cancellation rules. Expenses without a driver and ordinary journals keep native behavior.
- Migrated `cranes-dev2.arab-erp.com` and repaired missing Journal Entry parties for historical employee expenses, including `EXPE-00004` / `ACC-JV-2026-00004`. Amounts and ledger balances remain unchanged. Expense integration checks cover posting, cancellation, blank employees, repeatable backfill, conflicting parties, and ordinary journal validation; the existing rental workflow tests also pass. Restored the site's original disabled test setting.

- Added the submittable Treasury Transaction DocType with company, payment mode, resolved source account, destination cash/bank account, amount, references, description, and a protected Journal Entry link. Submission posts one balanced native Journal Entry using normal accounting permissions; cancellation reverses it, retains the historical link, and supports amendment. Added a Treasury Transactions workspace shortcut. Transfers require distinct enabled company-currency cash/bank accounts.
- Migrated `cranes-dev2.arab-erp.com`. All five treasury integration tests, both rental workflow tests, and all five expense integration tests passed. Coverage includes cash-to-bank and bank-to-cash posting/GL entries, direct journal cancellation protection, reversal/amendment, invalid amounts/accounts/payment modes, and rollback when Journal Entry create or submit permission is denied. Python/JavaScript syntax and whitespace checks passed; restored the site's original disabled test setting.

- Added **Crane Rental Profitability** and its Crane Operations report shortcut. It shows submitted rental invoice income, supplier hire costs, and cash/custody Expense Entries in company currency, with date/Assignment/Crane filters, source accounts, linked documents, totals, and income minus expenses. Taxes, drafts, cancellations, payments, and treasury transfers are excluded; native invoice returns reduce their source amounts and shared invoice links are counted once. Source read permissions remain required.
- Added an explicit, repeatable demo command and created one owned-crane cycle on `cranes-dev2.arab-erp.com`: Assignment `ASG-00065`, Timesheet `TS-00051`, invoice `ACC-SINV-2026-00011`, customer receipt, custody funding, and four submitted cash/custody expenses for 25–27 October 2026. Verified EGP 15,000 income, EGP 3,500 expenses, and EGP 11,500 net sales. Demo records are marked HER DEMO and never seeded by migration. See [SIMULATED_RENTAL.md](SIMULATED_RENTAL.md).
- Migrated `cranes-dev2.arab-erp.com`; all four report/demo integration tests and both rental workflow tests passed. Coverage includes paid invoices, cash/custody sources, date/crane filters, repeatable seeding, cancelled/draft expenses, sales returns, shared invoice deduplication, supplier costs/cancellation, and missing permissions. Verified the populated report through Frappe's native report endpoint, including its total row and summary cards. Python/JavaScript syntax and whitespace checks passed; restored the site's original disabled test setting.

- Fixed Rental Profitability's default monthly view crashing with `Journal Entry None not found` on historical submitted expenses `EXP-00003` and `EXP-00004`. Missing/deleted, unsubmitted, cancelled, or wrong-company journals now exclude their expenses with a visible warning listing the affected IDs. No historical records or ledger amounts are changed. Verified the full October report through Frappe's native report endpoint; all five report integration tests passed, including the new historical-journal regression test. No schema migration is needed; the site's disabled test setting was restored.

- Rebuilt rented-crane purchasing around worked hours. A rented Crane defaults the Timesheet's editable **Rented** checkbox to checked; unchecking persists and skips supplier invoicing. Checked Timesheets require **Purchase Price per Hour** and submit a native Purchase Invoice with Hour UOM, conversion factor 1, and actual distinct crane hours. Idle dates and overlapping drivers add no duplicate purchase hours. Removed the purchased-date-interval restriction while retaining submitted-shift overlap protection and existing customer billing terms.
- Added an idempotent migration that preserves historical posted invoices and submitted snapshots, archives previous interval purchase terms, and clears Day/Month purchase rates on drafts for hourly re-entry. Existing invoice cancellation, amendments, supplier payments, permissions, and profitability integration remain supported.
- Migrated `cranes-dev2.arab-erp.com`; all 10 purchasing tests, both rental workflow tests, and all five profitability tests passed (17 total). Coverage includes actual/fractional/overnight crane hours, overlapping drivers, hourly sales/purchase quantity agreement, Hour purchases independent of sales Billing Unit, opt-out persistence, owned cranes, overlapping periods with distinct shifts, invoice posting/payments/cancellation/amendment, denied accounting permissions, and repeatable historical-term migration. JavaScript selection/default/dependency checks, Python/JavaScript syntax checks, and whitespace checks passed. Restored the site's original disabled test setting.

- Added Billing Defaults to Heavy Equipment Rental Settings: Default Selling UOM and Default Supplier Billing UOM, each Hour/Day/Month and initially Hour. New Timesheets prefill their selling unit and the selected Crane's matching reference price; existing Assignment terms and user overrides take precedence. Supplier Billing UOM is captured on each Timesheet and determines the submitted Purchase Invoice UOM and purchase-price basis.
- Supplier Hour purchasing still uses actual distinct crane hours. Day counts distinct worked dates; Month prorates those worked dates by calendar month length. Idle period dates are excluded. Invoice stock-UOM conversion represents actual crane hours. Added a repeatable migration initializing missing Settings defaults and existing Timesheet purchase units from linked invoices (Hour without an invoice), preserving saved prices, invoices, and configured defaults.
- Migrated `cranes-dev2.arab-erp.com`; all 14 purchasing/defaults tests, both rental workflow tests, and all five profitability tests passed (21 total). JavaScript form checks passed for initial defaults, Crane pricing, unit changes, manual overrides, Assignment priority, saved forms, user edits during pending requests, and stale Crane responses. Python/JavaScript syntax and whitespace checks passed; restored the site's original disabled test setting.

- Added shared ownership and operating agreements to Crane's existing Ownership Type, with dynamic partner controls and separate ownership/profit percentages. Dated versions preserve historical terms; financial configuration requires Accounts Manager/System Manager. Existing Owned/Rented/Other records and supplier hire behavior are preserved.
- Added Crane Profit Settlement for consecutive period closure, posted source evidence, immutable agreed shares, loss recovery and currency rounding. External positive shares post native supplier Journal Entries; zero/loss periods retain their settlement without a journal. Partner Payment opens a native draft Payment Entry supporting partial/full allocations. Closed sources, duplicate periods, direct journal cancellation and cancellation of paid settlements are protected; corrections reopen periods backwards or post in an open period.
- Added optional Crane attribution on native Sales/Purchase Invoice Items and Journal Entry Accounts, including automatic attribution on new rental invoices. Settlement margin additionally supports ordinary attributed invoice items and salary/maintenance journal allocations; existing Rental Profitability scope stays unchanged. Migration adds fields/indexes without inferring agreements or distributing historical profit. See [PROFIT_SHARING.md](PROFIT_SHARING.md).
- Migrated `cranes-dev2.arab-erp.com`; all 45 integration tests passed: 14 new settlement tests plus 31 rental workflow, purchasing/defaults, profitability, employee expense and treasury tests. Coverage includes independent/multiple shares, dated changes and pauses, historical preservation, losses, returns, manual accounting sources, permission denial/rollback, duplicates, closed periods, partial/full payments, and synchronous posting/reversal of a 101-row partner journal. Browser checks passed for ownership-dependent controls, full-width partner tables, read-only settlement shares, linked source rendering, desktop/mobile layouts and no JavaScript errors. Python/JavaScript syntax, DocType JSON/order and whitespace checks passed. Restored the site's original disabled test setting.

## 2026-11-06 — Operating share before expenses

- Added Operating First agreements: allocated Sales Invoice Grand Total → operating percentage → posted costs → remaining-balance partner percentages. Ownership stays independent. Company is optional in the owners table; operator-only entitlements appear automatically. An operator/partner has separate operating and residual amounts and one combined native payable.
- Added Change Agreement with effective dates, collapsed accounting setup, clear settlement breakdowns and Arabic labels/deficit explanation. Existing histories/snapshots remain unchanged; migration marks legacy net-profit versions and fills only new historical display fields. New/changed terms use Operating First.
- Saving/submitting now rejects costs above the remaining balance, including a one-cent deficit introduced after a draft was saved. Negative revenue and non-finite/out-of-range operating percentages are rejected. Exactly zero remaining balance is allowed; no new loss is carried forward. Historical losses are retained and must be recovered before switching methods.
- Migrated `cranes-dev2.arab-erp.com`. Verified 53 integration tests across settlement (22), rental workflow (2), purchasing/defaults (14), profitability (5), employee expenses (5) and treasury (5). The app-wide runner used `--skip-test-records` because generated unrelated ERPNext fixtures reference the site's uninstalled optional Payment Gateway DocType; existing development fixtures and the normal controllers/ledgers were used. Python/JavaScript syntax, DocType JSON/order and whitespace checks passed. Restored the site's disabled test setting.
- Browser checks passed for the dated agreement action, operator-only partner entry, collapsed accounting controls, read-only source/share results, desktop and 390px RTL layouts, without page overflow or JavaScript errors. Temporary browser authentication was removed after verification.
- Created and paid three real development settlements: `CPS-00001` (one owner, 100,000 − 10,000 − 20,000 = 70,000; partial/full payment), `CPS-00002` (three partners, 35,000/21,000/14,000), and `CPS-00003` (dated operating/ownership/distribution change, 27,200/23,800/17,000). Partner balances and invoice outstanding amounts are zero; journal debits equal credits. Repeated the demo without duplicate successful documents/payments. A 1,000 deficit was blocked and that isolated scenario rolled back. The retained examples and explicit ledger reconciliation are in [OPERATING_FIRST_DEMO.md](OPERATING_FIRST_DEMO.md) and its JSON evidence. The 10,000 illustrative invoice tax makes contractual operating retention differ from accounting profit, explicitly documented for user review.

### Same-day clarification — no taxes and settlement meaning

- User clarified the rental scenario has no taxes. Replaced the current operating demo with separately identified `v2 No Tax` records, preserving all earlier submitted examples. Invoices are exactly 100,000 net and Grand Total, with no tax rows or tax ledger postings. Added a fixture-only rental duration parameter (default three days unchanged); the new sample uses one day at 100,000.
- Posted and paid `CPS-00004` (single owner), `CPS-00005` (three partners), and `CPS-00006` (dated changes). Native accounting results now equal company operating retention: 10,000 / 10,000 / 12,000. Verified balanced journals, zero partner/invoice outstanding balances and a blocked 1,000 deficit. Repeated the command and checked that submitted settlement/payment IDs remained unchanged. Existing rental workflow tests passed (2); Python syntax and whitespace checks passed. Restored the site's original disabled test setting. No schema or settlement calculation changes were needed.
- Updated the active numerical report and JSON evidence with these no-tax sources. Added an explicit explanation: the settlement is a period calculation/approval document; submission recognizes external partner entitlements with a Journal Entry, and a separate Payment Entry pays them. The company's operating share is retained without recording rental revenue a second time.

### Company as both owner and operator

- Replaced the blocking zero-company-ownership error for an Our Company operator with classification as Shared Ownership when the company receives positive ownership. The form reacts to ownership percentage, party flag and ownership-type selection; the server applies the same classification to saves from existing clients/API. Operating percentage and ownership/residual percentages are preserved. Zero ownership with an agreed residual share remains valid under Operated for Owner.
- Retained agreement permissions, later effective dates and historical snapshots. Integration verifies combined company entitlement of 1,500 operating + 2,000 residual = 3,500, external payable 8,000 from revenue 15,000 and costs 3,500, plus unchanged earlier terms and rejection of same-date ownership changes.
- All 23 settlement integration tests passed on `cranes-dev2.arab-erp.com`. Browser checks passed for percentage/party/type edits, zero ownership with a residual share, unchanged agreement history and no JavaScript errors. Python/JavaScript syntax and whitespace checks passed. No schema migration or automatic rewrite of existing records was needed. Restored the original disabled test setting and removed the temporary browser session.

For the next change: inspect `git status` first. Use the commands in [README.md](../README.md) for migration and tests, and update this page with meaningful new milestones.

## 2026-11-06 — LYD treasury workbook and development reset

- Created **شركة المعدات الثقيلة - ليبيا** (`HER-LY`, LYD) for the supplied `الخزينه.xlsx`, using the user's approved zero starting balances and date rules. Posted **93 Expense Entries + 79 Treasury Transactions**, each with its own submitted, balanced native Journal Entry. Created 15 expense types/accounts/cost centers and 10 payment modes, including six employee advance accounts, owner/staff current balances, cash custody and bank.
- Matched all **172 source rows** to their actual GL postings, including incoming/outgoing amounts, names, categories, descriptions, posting dates, sequence and running balances: **46,200 incoming − 46,180 outgoing = 20 LYD**. Operating costs are 37,369; advances 6,831; owner drawings/returns 1,980. Zero openings create no zero-value journal. Bank shows a 4,500 credit because the approved zero-start workbook contains outgoing bank funding without bank receipts; no unsupported bank opening was invented.
- Extended Treasury Transaction to explicitly designated custody/advance Asset and current Liability accounts; preserved native currency/company/account/permission checks and cancellation controls. Added **Treasury Workbook** to Crane Operations, with exactly seven visible columns, RTL, source links, workbook order, native period/opening balances, live cancellation handling, custom print and styled Excel download. Defaults open the latest accessible import without changing user defaults.
- Completed a full database/public/private-file backup before changes. After explicit user confirmation, deleted `cranes company` operational/accounting transactions, including linked Timesheets/Maintenance and GL/payment ledgers. Preserved all master names, other-company ledgers and the newly imported company. Explicit reset is limited to the approved development site, a backup and an unchanged deletion-plan fingerprint; never called by migrate/install. No shared naming series were reset. Earlier EGP demo transaction IDs are historical examples following this reset.
- Migrated `cranes-dev2.arab-erp.com`. **17 integration tests passed**: 5 workbook import/report tests, 5 treasury, 5 expense and 2 rental workflow; the workbook suite was rerun after final default-account/default-filter changes. Covered full posting/ledger reconciliation, repeat imports, rollback on posting failure, source cancellation, report permissions/period opening, formula/amount validation and styled export. Restored the site's disabled test setting.
- Browser checks verified 172 report rows and 20 LYD ending balance, workspace shortcut, seven visible columns, automatic import filters, 1600px and 390px layouts and no JavaScript errors. See [TREASURY_WORKBOOK.md](TREASURY_WORKBOOK.md), reconciliation, row mapping and deletion audit JSON files for exact evidence.

## 2026-11-06 — Cost Center on treasury movements and workbook filter

- Added optional Cost Center to Treasury Transaction, company/leaf/enabled validation and form query, and copying to both new journal rows. Preserved recipient attribution and existing account/cancellation permissions.
- Added the company-scoped Cost Center report filter, clearing it when Company changes. Expense/treasury source centers govern their rows; ordinary vouchers use the selected account’s actual GL dimensions without guessing counterparty allocations. Filtering applies to opening balances, totals, running balances, print and Excel output while retaining the seven visible workbook columns.
- Migrated `cranes-dev2.arab-erp.com`. Idempotent patch filled the 79 imported transfers’ missing source centers from explicit workbook categories, creating three centers (18 category centers plus the existing company Main center), preserving existing assignments and posted journals/GL. Updated future imports to set centers on every category. Verified 41 advance rows / 6,831 and 11 miscellaneous rows / 585; the unfiltered report still has 172 rows and 20 LYD.
- Passed 17 integration tests: 6 workbook/report, 9 treasury and 2 rental workflow. Covered filtered periods/openings/export, backfill repeatability and unchanged GL, valid journal attribution, and foreign-company/group/disabled center rejection. Corrected the existing party-amendment test fixture to honor No Copy fields, matching native amendment behavior. Restored the original disabled test setting.
- Browser verified the form's Cost Center field and company query, 41 filtered advance rows / 6,831 LYD, 41 print rows, successful filtered XLSX download, clearing the center on Company change, and no JavaScript errors. Removed the temporary verification session.

## 2026-11-06 — Treasury recipient on Journal Entry

- Added optional Party Type and Dynamic Link Party to Treasury Transaction, with registered ERPNext party choices, paired server validation and clearing the previous party when its type changes. New submissions copy the recipient to the destination debit row of the native Journal Entry; source rows and treasury GL balances retain no party. Persisting the source before journal submission keeps reposts scoped to the matching source, while ordinary journals retain native validation. Existing posted transfers/journals are unchanged.
- Migrated `cranes-dev2.arab-erp.com`. Passed 22 integration tests: 9 treasury, 5 employee expenses, 2 rental workflow and 6 workbook/report. Covered Employee/Supplier/Customer recipients, cash/bank and designated custody/advance/current accounts, balanced posting, GL mapping, native validation on copied ordinary journals, cancellation/amendment and permission-failure rollback. The expense regression run supplied a missing Employee fixture inside the test transaction; it was rolled back afterward.
- Passed JavaScript checks for registered-party queries and clearing stale parties, DocType field order/Dynamic Link checks, Python/JavaScript syntax and whitespace checks. Tests ran without changing the site’s disabled test setting.


## 2026-11-09 — Settlement uses source revenue accounts

- Operating First settlement journals now reduce the source invoice/income-journal Income accounts, apportioned over signed revenue with exact currency rounding. Source snapshots retain account and accounting dimensions, and the source table exposes revenue account links. Legacy Net Profit keeps its prior allocation account. Hide the obsolete allocation selector for Operating First and stop requiring it for new agreements.
- Preserve Crane and other accounting dimensions. Register each generated journal on its controlling settlement before submission, so it may close its own period while direct cancellation, source locks and exclusion from future source totals remain enforced.
- Migrated cranes-dev2.arab-erp.com. Passed 26 settlement integration tests plus 2 rental workflow tests, Python/JavaScript syntax checks, source-table rendering/escaping checks and whitespace checks. Covered multiple income accounts, partial returns, source cost centers, signed credit allocations, partial/full partner payments, journal permissions, historical treatment and cancellation/amendment. Test records were rolled back and the site's disabled test setting was retained.
- Corrected only CPS-00007 after an exact rollback rehearsal and private JSON backup: native cancellation retains CPS-00007 / ACC-JV-2026-00211, and amendment CPS-00007-1 posts ACC-JV-2026-00212. Debit Sales - CC 97,771.20 EGP; credit Creditors - CC / Mohamed fahmy 97,771.20 EGP. Revenue remains 203,690; company retained 105,918.80; source/share amounts, partner payable balance, customer receipt and all cash/bank balances remain unchanged. Backup and correction result are in the site's private/backups/CPS-00007-*-revenue-correction*.json files. No partner payment was created.


## 2026-11-10 — Automatic Timesheet settlements, Shareholders and partner statements

- New sharing Timesheets create one linked draft settlement with the Crane/work dates. Sales Invoice submission automatically approves/posts the settlement and native entitlement journal in the same transaction, as explicitly chosen by the user. Shared invoices and overlapping work costs allocate deterministically without double distribution; snapshots retain weights/candidates. Deficits and missing journal permissions roll back invoice approval. Preserve period closures and historical loss controls.
- Added native Shareholder partner/operator selection, supplier-to-Shareholder mapping and Company-specific Partners Payable defaults, including Shareholder party accounts. Migration backfills current identities and historical Timesheet links, preserving submitted sources, agreement snapshots, journal/payment amounts, original ledger party/account and period closure behavior. No historical entitlements were posted again. Historical Supplier balances remain payable through their original journals.
- Settlement displays live posted/pending entitlement, paid/adjusted amount, outstanding status and draft/submitted Pay entry links. Partner Payment uses the remaining ledger balance, selects an unpaid partner when several remain, and fills settlement/Timesheet/Crane links on the native draft Pay entry. Validate the selected partner/reference and serialize allocation against the settlement journal. Ordinary supplier purchase payments retain their native behavior.
- Added Crane Partner Statement (detailed movements with totals) and Crane Partner Summary (Shareholder totals and 30-day aging bands) to Crane Operations, plus Shareholders. Include invoice values, entitlement/payment status, native as-of-date balances and Company/period/Shareholder/Crane/Timesheet/status filters. Full invoice values display separately from totalable allocations. Respect source, payment and partner read restrictions; preserve pending status even before invoice values exist.
- Migrated cranes-dev2.arab-erp.com and ran the repeatable identity/link backfill. **51 integration tests passed**: 26 existing settlement/accounting tests, 9 automatic Shareholder/report tests, 14 Timesheet/purchasing tests and 2 rental workflow tests. Covered invoice/entitlement rollback, shared sources and costs, selected operator vs legacy aliases, partial/full/cancelled payments, historical report dates, migration repeatability, duplicates and permission failures. Test records were rolled back; the site's disabled test setting was retained.
- Live browser verified settlement balances/Shareholder display/payment action, detailed and summary reports with their native total rows, summary aging columns, desktop/mobile render and no JavaScript errors. Both reports and the native ledger showed the existing **97,771.20 EGP** outstanding balance. Exercised the two-partner selector with controlled responses without saving a payment. Removed the temporary verification session. Python/JavaScript syntax, JSON field order and whitespace checks passed.


## 2026-11-10 — Development company transactions cleared

- On the user’s explicit request, reset only `cranes company` on `cranes-dev2.arab-erp.com` using the existing guarded development reset command, after a full database/public/private-file backup (`20261110_231135-cranes-dev2_arab-erp_com-*`).
- Removed 3 Sales Invoices, 2 Payment Entries, 2 Journal Entries, 16 GL Entries, 8 Payment Ledger Entries, 3 Crane Profit Settlements, 3 Assignments and 3 Timesheets. All transaction types in the reset plan now have zero company records.
- Verified master records (including Shareholders) and other-company accounting sources/ledgers were preserved. Only the target Company’s cached monthly sales values and modification metadata were reset. Shared naming series and application code were unchanged. See [deletion audit and backup checksum](DEV_COMPANY_RESET_20261110.json). Earlier demo balances and transaction IDs above are historical following this reset.

## 2026-11-13 — Directed rental cancellation

- Corrected cancellation scope to follow Timesheet → invoices → settlements. Invoice cancellation keeps its Timesheets submitted; settlement cancellation keeps invoice/work submitted and reverses only its own entitlement journal. Timesheet cancellation includes its invoices and settlements. Historical backlinks do not expand the scope.
- Confirmation previews deduplicated documents, rejects changed scope and executes atomically with normal permissions/accounting guards. Paid entitlements retain the existing cancel/unreconcile-payment requirement.
- Two development regression tests passed, covering all three starting documents, upstream document preservation, duplicate removal, stale confirmation rejection and rollback after an accounting failure. Syntax and whitespace checks passed. No schema migration required; restored disabled tests and cleared site cache. No business documents were cancelled by this implementation task.
