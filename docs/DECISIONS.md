# Current decisions

## 2026-11-17 — Consolidated expenses (مصروف مجمع)

Added a submittable Consolidated Expense with one Crane/Timesheet/Rental Contract, optional Driver, company Cost Center and default payment method. Dated rows show description/total inline; type and payment overrides stay in the pencil editor. A fixed bilingual XLSX template supports download and validated draft-row upload. HER Settings holds company expense defaults; portable setup seeds the عام account/type only into missing defaults. Submit/cancel delegates each row to the existing Expense Entry and native journal lifecycle, preserving CPS attribution, period closures and atomic rollback without counting costs twice. The highlighted workspace link replaces Expense Entries; historical sources remain accessible. See [usage and accounting](CONSOLIDATED_EXPENSES.md).


## 2026-11-17 — Employee dates

Hide Date of Birth and make it optional in Employee metadata so both forms can save without it. Use Frappe's Today default for the editable Date of Joining on new Employee records. Preserve stored dates.

## 2026-11-17 — Timesheet driver payroll

Use the shared Expense Entry and native Journal Entry workflow. The configured Expense Entry Type supplies the salary expense account and the Mode of Payment supplies the funding account. Each positive amount posts on Timesheet submission using the submission date. Blank and zero amounts skip posting and require no defaults. Cancel the Timesheet to reverse its generated expenses and retain their history. An amendment carries the amounts forward and creates fresh entries on submission.

Store Mode of Payment on each payroll row and show it in the pencil editor. Use the company payroll default for empty rows and allow a per-driver override. Posted rows take their historical mode from the linked Expense Entry during migration.

Show one Driver Payroll grid above Totals. The quantity and price columns follow the Timesheet billing unit, using actual hours, distinct worked dates, or calendar-month fractions. Legacy Timesheets with mixed shift units and no sheet unit use hours. Editing the rate calculates the amount. Editing the amount fixes the amount and derives a rate when quantity is positive. Keep the earlier hours fields for stored history and integrations. Totals displays Total Crane Billable Hours and Total Amount.

## 2026-11-17 — Future Crane Timesheet dates

Crane Timesheets accept future periods and operator shifts in drafts and on submission. Each shift still has to fit within the Timesheet period and the booked crane dates.

## 2026-11-17 — Crane Operations site entry

HER owns the Crane Operations entry redirect through a Frappe request hook that runs on every site where the app is installed. Browser GET and HEAD requests for `/`, `/app` and `/app/` receive a 302 to `/app/crane-operations`. Frappe handles authentication, API calls, and direct Desk links. Caddy retains the deployment maintenance response.

## 2026-11-16 — App manifest for image and site installation

The repository-root apps.yaml now selects the Frappe branch and ordered app name/repo/ref entries. CI resolves refs to immutable build inputs; HER uses the exact tested checkout. Image builds, new-site installation, existing-site app additions and health checks share that manifest. Installed apps are never silently removed; removing one from the manifest fails safely under the existing snapshot/rollback transaction. Branch refs track upstream on runtime builds; use full app commit refs to pin versions. This replaces deploy/dependencies.json. The version-15 stack retains ERPNext, arab_erp_theme and HER as required dependencies. Verified 13 deployment/manifest tests, 33 workflow tests, and successful automatic production deployment. The running image manifest and production health were checked. Frappe (optional frappe_ref) and ERPNext are explicitly held at the previously validated commits: tracking the latest branch heads exposed a repair double-capitalization regression and CI blocked that upgrade. [Successful workflow](https://github.com/00JIMMY00/heavy_equipment_rental/actions/runs/43940164215).

## 2026-11-16 — Docker production delivery (verified)

Production is live at https://cranes.arab-erp.com on the ARM64 Hetzner host 49.12.190.89 (`hetzner3`), stack `/opt/her`, with Frappe, ERPNext, arab_erp_theme and HER. It started clean, with no development business data; Administrator login and the native setup wizard are available. Developer mode and production tests are disabled.

Pushes to main now validate, build/test native ARM64 images, publish an immutable GHCR digest, and deploy through restricted SSH. Pinned framework/theme dependencies and their assets occupy stable image layers; HER updates transfer small separate layers. Documentation-only pushes validate without deploying. CI tests the production configurator with empty bind mounts, installs/migrates all apps, and passes 33 current workflow tests plus 8 rollout tests. The older partner suite contains superseded service-date and implicit-sharing expectations and is outside this release gate. Fresh installation also exposed/fixed first-time Workspace insertion.

Verified a normal automatic update and a forced post-migration failure. Recovery restored SQL, site files and configuration, recreated bind mounts, removed database/file/configuration probes, and passed health and login checks before reopening traffic. Keep the current and previous successful HER images and five complete recovery snapshots; never prune data volumes. [Verified run](https://github.com/00JIMMY00/heavy_equipment_rental/actions/runs/43907282490), [evidence](PRODUCTION_DEPLOYMENT_20261116.json), [operations](../deploy/README.md).

## 2026-11-16 — Full-screen Arabic login (latest)

Revised login to fill the viewport with white, pale sky blue and soft yellow, local crane photography and a locally hosted Cairo Arabic font (OFL). Arabic is the default for guest GET /login requests, even with English browser/cookie preferences; explicit _lang remains available. The request hook does not change stored user or site language settings. Login stays light regardless of the OS theme. Added conversational Arabic copy and retained native authentication, recovery, email-link and signup flows. Supersedes the centered navy login design. No schema migration required.

## 2026-11-16 — Unified Arabic Timesheet terminology

Use «تايم شيت» consistently for Timesheet, Crane Timesheet, plural Timesheets, Crane Work Log and Equipment Work Log. Updated app translations, related messages, reports and timeline category. Legacy Arabic Timesheet labels resolve to the same wording, while Timeline retains «الجدول الزمني». Internal DocType names, IDs and data remain unchanged. Supersedes earlier «سرك» / «سجل العمل» terminology.

## 2026-11-16 — Compact crane timeline

Replaced the timeline hero, summary cards and repeated legends with a compact heading, period controls and counted activity toggles (only types with records appear). Default grouping is one row per Crane. Contract-scoped URLs automatically fit the booked dates (one day padding, bounded to the existing 120-day range limit). Filters, search and custom dates are collapsed behind Filters. Timeline day columns fill available width for short bookings and scroll for long ranges; reduced sticky resource width. Clickable event details/native links and Escape dismissal remain available. Added Arabic timeline controls/date labels using the user's existing language, preserving theme and backend permission checks. No rental data or billing logic changed.

## 2026-11-16 — Rental Contract rename (latest)

Renamed Crane Assignment in place to Rental Contract, Arabic «عقد ايجار معدة». A pre-model migration uses native DocType rename to retain existing IDs, child rows, permissions and all rental links. Existing ASG numbers remain valid; new documents use RC-.##### (legacy naming series remains accepted for saved records). Updated controllers, linked field labels/options, dashboards, workspace seed/saved links, reports, messages and calendar source. Stable internal assignment/crane_assignment fieldnames and API parameters remain for historical/integration compatibility; old Python controller imports forward to the new module. Current document route is /app/rental-contract. The old documentation below records prior milestones.

## 2026-11-16 — Full-width maintenance repair table

Removed the repair_column layout divider from Crane Maintenance. Items / Services spans the full width within the original Repair Items section; supplier details remain above the table. Section visibility rules and repair accounting behavior remain unchanged. Applied metadata migration to dev3.

## 2026-11-16 — Employee names in driver links

Enabled Employee show_title_field_in_link using the existing employee_name title field. Native Employee Link controls and grid cells, including Timesheet Entries drivers, display employee names while saving the same Employee IDs. HER setup persists the Property Setter; existing payroll, shifts and employee references are untouched. Reload Desk after applying to refresh boot link-title settings.

## 2026-11-16 — Minimal Employee creation

Enabled native Employee Quick Entry with Employee Name (stored in first_name), Date of Birth, Status and Date of Joining. Company uses native defaults and is requested only when missing. Gender defaults to Male and is hidden; Salutation is hidden. Existing employee values are preserved. Full-form advanced employment fields and native validation remain available. HER setup installs Property Setters, and a scoped Employee QuickEntry subclass controls only the creation popup.

## 2026-11-16 — Restore standard Item Details visibility

Moved the HER Crane Period Prices custom section from after standard_rate to after uoms, at the end of the native Details tab. Its crane-only depends_on previously swallowed the intervening native Item fields into a hidden section for ordinary Items. Item Group, stock UOM, Maintain Stock, Is Fixed Asset and related standard options now retain ERPNext's native visibility and edit rules. No inventory or asset values are changed. Setup updates the Custom Field placement on existing sites and future migrations.

## 2026-11-16 — Crane list render fix

Ownership before_render now passes Crane to frappe.get_list_view, with a missing-instance guard. The previous missing argument resolved no list instance and stopped row rendering. Browser verified all nine Crane rows and segmented/rental ownership bars in Arabic; focused rendering-hook regression and syntax/whitespace checks passed. Existing unrelated null/join startup errors remain observable but do not prevent the list rendering.

## 2026-11-16 — Native rental Location links

Assignment and Timesheet Location fields now link to ERPNext Location. Assignment selection still fills the Timesheet location, and matching requires the same Location record. Migration creates missing native Locations from historical text and changes references only if native naming normalizes the value; submitted work, dates, rates and modification timestamps remain intact. Applied to dev3 and verified every saved rental location resolves. New entries use the native searchable Link control and normal Location permissions.

## 2026-11-16 — Crane list ownership column

Replaced Model in default Crane list columns with Ownership: compact classification and segmented owner-share bar, with owner/percentage tooltip. Supplier-hired cranes show their rental classification and orange bar instead of retained ownership shares. Shares are batch loaded only for permission-visible cranes. Model stays editable in the form. Applied metadata migration on dev3; verified endpoint permissions and list metadata.

## 2026-11-16 — Invoice deletion circular-link fix

Sales/Purchase Invoice on_trash clears only its managed Timesheet reverse link for draft/cancelled documents. Invoice cancellation retains historical links using the existing narrow ignore rule. Other native payment, settlement and repair links remain protected. Draft ACC-SINV-2026-00007 backed up privately and deleted at user request; TS-00008 and TS-00009 remain submitted with empty sales_invoice links. Regression verifies draft deletion and regeneration. Workflow suites: 18 passed, one legacy test skipped.

## 2026-11-16 — Supplier rental classification

Hired from Supplier takes precedence over retained owner rows: classification is Hired from Supplier and compatibility type Rented. The form shows the supplier instead of a company share bar and hides the ownership table. Migration corrects existing hired cranes including CR-00009 without deleting ownership rows or dated agreements.

## 2026-11-16 — Editable rental units through sales billing

Crane now stores an editable Default Selling UOM, initially filled from HER Settings. Assignment rows inherit the Crane unit and matching reference price; explicit choices remain editable. Timesheets inherit Assignment terms as visible defaults, with editable unit/rate overrides retained on save and used for shift amounts and sales billing. Submitted Timesheet terms are the billing snapshot; changing a master default does not reprice existing work. Sales Invoice lines use the actual Hour/Day/Month quantity and agreed unit rate, with actual crane hours as the stock-UOM conversion and nine-decimal sales quantity precision for monthly fractions. Conflicting flat billing terms for the same booked crane/day are rejected to prevent duplicate charges. Supplier billing remains independent.

Migration fills only missing Crane defaults, preserving historical rentals and invoices. The user's draft ACC-SINV-2026-00007 was backed up and corrected from 1 Hour × 4,500 to 3 Day × 1,500 for CR-00009; its other line and total 9,000 are unchanged.


## 2026-11-16 — Crane ownership share bar

Replaced the Crane Ownership field’s plain classification and technical description with a segmented owner share bar. Each owner has a colored segment plus a name/percentage legend, using Shareholder titles when permitted. Updates on ownership, owner selection, add/remove and form refresh. Incomplete draft totals show an explicit warning. Classification, validation, ownership/profit calculations and historical agreements remain unchanged; no schema change.


## 2026-11-16 — Shallow regenerated panorama (latest)

Regenerated the crane image with distant vehicles and low booms composed for a shallow panoramic strip. The workspace now uses `cranes-panorama-v2.png`, displayed at 10:1 with a hard maximum height of 25vh/25svh and a focal position of 62%. This supersedes the tall 3:1 banner. Sections/الأقسام remains removed.


## 2026-11-16 — Full crane banner

Increased the crane banner from 10:1 to the image’s native 3:1 ratio and used contain sizing so all three cranes remain visible without cropping. Removed the Sections/الأقسام heading from the template and dev3’s saved workspace. Existing site edits are preserved.


## 2026-11-16 — Requested workspace wording and banner

Renamed Rental Operations in Arabic to «عمليات على الونش», with links ordered «سرك الونش», «صيانة الونش», «تكليف الونش». Removed the separate Maintenance card, Quick Access, overview text, top Customize/Refresh actions and bottom Timesheet/Maintenance reports. Added a generated crane photo displayed at approximately 10:1. Native bottom Edit remains available. Applied to dev3 after a private workspace backup; migration persistence remains unchanged.


## 2026-11-16 — Arabic interface audit

Extended the app Arabic catalog with current workspace, rental, maintenance, asset, settlement, payment and validation text. The reference workspace overview and custom actions now translate in Arabic mode. Preserve internal document naming patterns and user-entered record names; translate interface text through the app Arabic catalog. Arabic browser checks showed no English UI words in the workspace; the new Crane form labels also translated. Global Frappe/ERPNext labels use their installed Arabic catalogs. Stored user-entered names, IDs and currency symbols are data and remain as entered. Clear site cache after updating translations.


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

General Ledger rental filtering uses existing voucher links rather than adding synthetic profit postings or rewriting GL Entry. A shared voucher is displayed at its full posted value; the report explicitly warns that CPS allocations are not prorated. Company/Crane mismatches are rejected. The standard report is extended through HER Report controller and get_script hooks; a request-local native module adds SQL voucher conditions without globally patching ERPNext.

- Expense Entry rental pickers now send only Posting Date, Crane, Company and an explicitly selected Assignment. No empty From/To filters appear. Work choices must include that one posting date; changing it refreshes/clears invalid selections. Maintenance behavior and submitted allocation snapshots are unchanged. Verified frontend filter arguments/date changes and native search against live Timesheet dates; syntax/whitespace checks passed. No schema change.

- Latest date clarification: Expense Entry uses Posting Date as its single expense date. Its legacy service From/To fields remain stored but hidden and ignored for expense date calculation; assignment/timesheet selection no longer fills a range. Explicit rental links remain authoritative. Maintenance retains Actual Start/End dates and its repair-period behavior. Historical submitted snapshots are preserved.

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

## 2026-11-15 — Explicit expense attribution for CPS (latest)

- Maintenance and Expense Entry costs require explicit rental links for CPS: a Timesheet charges only its settlement and fills Assignment; Assignment alone shares the cost across its submitted crane Timesheets by working hours. Neither link means a general, unallocated crane expense excluded from CPS. Dates do not choose or automatically fill the charged work. Mismatched links are rejected. Submitted settlement snapshots and ledgers remain unchanged; corrections use Cancel and Amend.
- Remove date-based form autofill and use explicit links for pending repair/expense closure checks. Preserve protection of sources captured by historical settlements. Legacy Period settlements still prorate linked costs by service days; unlinked costs are excluded. No historical links are inferred or cleared.

## 2026-11-15 — Native Maintenance Submit / Cancel / Amend (latest)

- Maintenance is submittable. Draft saves do not post; Submit completes the repair and posts its automatic purchase/stock/Asset Repair/payment documents or cash Expense Entry. Manual native-document repairs validate their posted documents on submission. Remove Complete Repair and direct Completed status editing.
- Cancel previews owned repair dependencies and reverses payments, newest Asset Repairs, stock issues, invoices and cash expenses/journals in order. Check normal cancel permissions first; fail atomically on closed periods, later repairs or any native accounting error. Prior My Stock purchases remain outside the cancellation. Shared payments involving unrelated documents and non-payment adjustments require explicit separate resolution.
- Amend retains repair inputs and clears generated links before native link validation. Corrected dates flow to new invoice/stock postings. Existing completed or posted Maintenance becomes submitted through a metadata-only patch; old cancelled rows become cancelled, original status/docstatus is archived and no historical posting is rerun.

## 2026-11-15 — Rebuild completion around Maintenance (latest)

- Automated sources support both Operating Expense and Capitalize Improvement. Complete Repair saves the form and posts all required native purchase, consumption, Asset Repair and supplier payment documents atomically. Parts purchases capitalize through stock consumption only; service invoices capitalize through Asset Repair service cost.
- Keep source and purpose together; automatic purpose choices are routine expense or improvement. Hide accounting defaults under Advanced Accounting and remove the direct Completed status choice for unposted automated jobs. Keep Manual Documents for legacy/other native workflows, preserving posted history.

## 2026-11-15 — Simplify repair defaults and supplier payment (latest)

- Routine repairs automatically use Operating Expense. Manual Documents explicitly replaces the empty source choice; Accounting Treatment remains visible in Maintenance Details: read-only for automated sources or posted/completed repairs, selectable for unposted Manual Documents. Cost Center remains under Advanced Accounting. Migration labels historical empty sources without changing posted documents or modification dates.
- HER Settings → Maintenance Defaults holds one row per Company for repair Expense Account, optional warehouse override and default supplier Payment Method. External parts automatically receive/consume through a company Maintenance warehouse (created/reused on posting when no override exists); only My Stock asks for row warehouses.
- Supplier Paid Amount defaults to the full native invoice amount. Partial and zero payments are supported; positive amounts submit a linked native Payment Entry with the purchase/issue/completion atomically. Native permissions, outstanding limits and cancellation order remain enforced. Existing completed repairs receive no retroactive payments.

## 2026-11-15 — Post routine repairs from Maintenance

- Operating Expense adds Repair Source and embedded item rows. My Stock posts Material Issue; External Parts posts a stock-updating Purchase Invoice followed by Material Issue; External Service posts a service Purchase Invoice. No second cash expense or automatic payment. Native valuation is authoritative.
- Explicit Post Repair & Complete posts atomically with native permissions and period guards; duplicates and edited generated links/financial inputs are blocked. Cancel issue before purchase. Existing blank-source/manual jobs and historical ledgers remain intact. Complex native workflows remain available; Connections shows related documents.

## 2026-11-14 — Rental eligibility and company selection

New/changed bookings and draft Timesheet validation reject cancelled, Sold, Scrapped or Capitalized linked Assets. Preserve historical links and cancellation. New Assignments derive a single company from their cranes; mixed-company bookings are rejected. Timesheet-first explicitly supplies the crane company. New maintenance derives company from selected work or crane; existing inconsistent company edits are rejected.

## 2026-11-14 — One Cancel action for rental dependencies

- Use the existing Cancel button on Expense Entry, Profit Settlement, Sales Invoice and Timesheet. Preview all linked submitted payments, affected/later period settlements, invoices and generated journals; confirmation reverses the listed accounting atomically with native permissions. A combined Payment Entry cancels in full, reopening its allocations to other documents. Non-payment reconciled journal adjustments require explicit unreconciliation first.
- Expense cancellation preserves its invoice/customer receipt/work; settlement cancellation preserves expense/invoice/work. Invoice cancellation includes its customer payments. No extra correction/recalculation buttons. Use native Amend for replacement expenses and settlements, then review/submit in dependency order. Preserve cancelled history and update the Timesheet backlink on settlement submission.


## 2026-11-14 — Expense amendment journal link

- New Expense Entry amendments clear only the cancelled source expense's copied generated Journal Entry link before native link validation. Preserve the original document/link and native amendment validation; unrelated supplied journals remain rejected.
- Use native Cancel → Amend → Submit. Reopen affected settlements first, resolving partner payment allocations explicitly. Keep the Sales Invoice and Timesheet submitted for expense-only corrections; recreate the settlement after correcting costs. The later One Cancel action decision supersedes the manual dependency steps.


## 2026-11-14 — Select multiple partner entitlements in Payment Entry

- Add a permission-checked picker to draft Pay entries for Shareholder/Supplier. Scope open, submitted settlement journals by Company, party and Account Paid To; optionally filter settlement posting dates, Crane, Timesheet and Sales Invoice. Amounts are current native ledger balances, not historical as-of balances. Exclude draft/cancelled/fully paid settlements.
- Append selected native Journal Entry references without duplicates. Preserve an entered payment amount; otherwise default to the total selected balance using payment exchange rates. Partial payments allocate in reference order, capped by each remaining balance. Extend the Shareholder allocator to multiple settlement journals; retain native behavior for other payment flows.
- Validate all participating settlements and retain native outstanding/submit locks. Combined payments clear the single-settlement/Timesheet/Crane header links; reference rows remain authoritative for reports and balances. No schema or historical accounting changes.

## 2026-11-14 — Partial partner payment from the settlement form

- Keep native Payment Entry and its accounting/permission checks. A scoped controller override allocates edited payment amounts for the single Shareholder Journal Entry reference created by Partner Payment; ERPNext v15 otherwise resets this allocation to zero because its positive-payable branch only includes Supplier/Employee.
- Respect the allocation toggle, deductions and outstanding cap. Other payment flows retain the native allocator. No historical accounting changes or schema migration.
- The Partner Payment button returns a native Promise so Desk can restore the button without a `response.finally` error.

## 2026-11-13 — Comprehensive profit distribution report

- Add native Script Report Crane Profit Distribution, accessible from Crane Operations, the Crane hub and settlement View. Five views cover settlement economics, participant totals, per-settlement percentages/cost burden, source costs/revenue and native payable/payment movements. Keep the existing partner and accounting reports.
- Read saved agreement/source/share snapshots, without recalculating or posting. Company operating and residual shares remain separate; expense burden follows saved residual-profit percentages, not ownership percentages. Company retention is not a payable or cash balance. Costs are explanatory allocations, never extra GL postings.
- Work-period filters select whole overlapping settlements; posting-date filters select settlement posting dates. Payment balances use the native ledger through Balance As Of. Separate posted/draft totals and estimates; never total percentages or running balances. A Shareholder/status filter scopes settlements, keeps full-context economics cards and limits participant/movement rows to matching partners. Do not repeat invoice/settlement totals per participant.
- Respect source, settlement, party, journal and payment read permissions; fail on inaccessible contributing documents rather than returning incomplete totals. Cancellations/delinked rows follow the current native ledger; no reconstruction of a previous cancellation state. Company currency only. Native export/print remain available.

## 2026-11-13 — Demo accounts must not become shared rental defaults

- Demo-specific invoice accounts belong to their example transactions. Preserve shared rental Item income defaults around explicit demo creation, because native SellingController learns non-company accounts when the Item default is empty. The shared development Item uses company Sales - CC for ordinary invoices. Submitted invoices require normal accounting correction; changing an Item default does not rewrite them.

## 2026-11-13 — Restore pre-550f4f5d profit distribution (latest)

- User explicitly requested the earlier settlement workflow. New agreements use On Invoice Submission, Source Revenue Accounts, Invoice Grand Total and no depreciation deduction. The invoice automatically posts the entitlement journal: debit source Income accounts, credit Partners Payable by Shareholder. Customer receipts and manual partner payments remain separate native Payment Entries.
- Hide the redesign's alternative accounting/approval/tax/depreciation selectors; keep their stored fields and calculation paths solely for historical compatibility. Legacy Profit Allocation Account is visible only for Legacy Net Profit. Costs Reviewed appears only on historical review-mode settlements. Asset ownership, stock/repair workflows, source locks, permissions and Connections remain supported.
- Migration appends restored dated terms after previous versions and submitted settlement periods, preserving original agreements, submitted settlements, journals, payments and GL. Do not reclassify paid historical entitlements. Record costs and complete operating repairs before invoice submission; deficits still block automatic entitlement posting and roll back invoice submission.

## 2026-11-13 — Complete Crane connections

- Keep the native Connections dashboard, using its supported custom count method. Discover incoming Crane links in standard/custom fields and child tables (including site accounting dimensions); show child links under their parent DocType. Include outgoing master/owner links, union header/row links and deduplicate documents. Counts and list destinations respect source and target permissions.
- Connections also follow linked Asset acquisition invoices/receipts, Timesheet invoices, expense/settlement journals, depreciation schedules and exact native Payment Entry references. Include invoice/journal rows attributed to the Crane’s selected company leaf Cost Center only when no other Crane shares that center; this includes dedicated spare-parts purchases. Never expand by shared supplier, customer or Item. Check read permissions at every hop and deduplicate results. No accounting or schema changes.

## 2026-11-13 — Company assets only (latest user instruction)

- Supersedes whole-crane/shared and custody recognition. Owned means full Company cost. Shared equipment means only the Company interest, using ownership_partners. No Company ownership means no Asset link or creation action. Basis is derived/read-only; Whole Crane, Pending Review and custody choices are removed.
- Asset panels show Company values only, with no other-owner amount allocations. Native accounting records our recognized costs; changing a percentage does not rescale posted Assets. Migration archives obsolete zero-ownership/custody and full-crane partial-interest links without rewriting Assets, agreements, settlements or GL.

## 2026-11-13 — Native workflow redesign and Crane hub (latest)

- User confirmed contracts vary: support both whole-crane control/funding and separately owned interests, with explicit accounting review. Asset Recognition Basis controls interpretation, not automatic postings or rescaling. Third-party custody cannot receive company capitalization/depreciation. This supersedes the earlier whole-cost-only decision.
- Crane → Operations is the main entry point. Keep native Asset, fixed-asset Item, stock Items/Warehouses, invoices, journals and payments. New cranes reuse one non-stock rental-service Item; historical per-crane Items remain linked. No custom stock, asset or contribution ledger.
- Extend existing Crane Maintenance with Operating Expense, Capitalize Improvement, Recover from Owner, No Cost and legacy Cash Expense. Native Material Issue consumes routine parts, Purchase Invoice records external services, Asset Repair capitalizes justified improvements, and stock-updating owner Sales Invoice records separately recoverable parts/services. Do not charge one repair through two treatments. Capitalization uses actual stock valuation, reverses with its stock issue, and retains native depreciation schedules.
- New dated agreements default to Review Before Posting, Net Revenue, Partner Expense and posted depreciation. Select a reviewed allocation account. Explicit Source Revenue Accounts and Equity Distribution remain available for appropriate contracts; external operating fees cannot be posted as equity distributions. Historical automatic approval, revenue basis and postings remain unchanged until a dated amendment.
- Review-mode deficits remain visible in drafts without blocking customer billing; submission still rejects deficits. Costs Reviewed and completion of relevant operating repair jobs are required to close reviewed settlements. Entitlement recognition and actual payment remain separate. Native repair costs allocate by work/service period; Rental Profitability uses accounting dates and includes repair stock/service costs and attributed depreciation/journals.
- Migration preserves physical Assets, stock, invoices, GL, current legacy Item links and immutable agreement/settlement snapshots. Existing cash maintenance stays Cash Expense. See [full design and boundaries](NATIVE_CRANE_WORKFLOW.md).

## 2026-11-13 — Crane fixed assets and shared ownership value

- The user explicitly chose **whole crane cost in our company's books** for shared cranes. Link the Crane to one native ERPNext Asset (quantity 1); keep its physical fixed-asset Item separate from the rental service Item. ERPNext remains the source of asset acquisition, depreciation and disposal accounting.
- Show live gross cost/current value after depreciation in company currency, using the company default Finance Book. Allocate reference values using the saved ownership agreement effective today, never profit percentages or future terms. Use deterministic currency rounding; missing book values are unavailable, not zero. These are reference values, not capital paid, partner liabilities or payments.
- Accounts Manager/System Manager controls new/corrected links, with native Asset read permission. Enforce one Asset per Crane in validation and through a unique database column; require Agreement/Asset Company consistency and explicit third-party ownership for Rented/Operated for Owner. Recheck consistency on native Asset validation. Crane's native change history audits link corrections; do not require cancellation of a valid Asset to correct master-data attribution. Preserve links/status through cancellation/disposal until explicitly corrected.
- Schema migration adds an optional link and financial HTML display only. Do not create/backfill Assets, costs, openings or journals from historical rental prices/ownership. Existing Cranes remain saveable without a link. Contributions/acquisition funding and any contractual depreciation allocation require explicit native accounting; this link does not alter posted settlements or deduct depreciation automatically.

These reflect the latest user requests and current implementation (2026-11-06):

1. Keep the rental workflow centered on **Crane Assignment** and **Crane Timesheet**. Do not restore the custom `Crane Project` or its old status workflow.
2. A Timesheet has one crane. When no Assignment covers its period, saving creates one using `period_start` and `period_end`; new Timesheets default the selling unit from Settings and the matching Crane reference price, with editable overrides before creating an Assignment.
3. Drivers are ERPNext Employees. The Timesheet's default driver is optional; individual shift rows may use another driver. Show employee names in the child tables and calculate per-driver hours from shifts.
4. Use a normal Attach field for the Timesheet hard copy, editable after submission. Use Frappe's built-in dashboard for Connections.
5. Billing uses submitted Timesheets and the rate on the Assignment. Preserve overlap checks and avoid double counting crane time when driver shifts overlap.
6. Retain migration patches for legacy records and uploads. Older design documents in the repository can conflict with these decisions; the latest user instruction and current code take precedence.
7. Crane master data includes a license plate. Its active reference prices are Hour, Day, and Month within Crane Details. Historical Year prices are archived in a hidden field during migration. Connections uses Frappe's native dashboard.
8. The Crane image is uploaded from the side panel and must be public; the form has no image section. The linked ERPNext Item shows a read-only copy of Crane period prices. Availability uses a compact monthly reservation calendar and appears only after the Crane is saved.
9. Show the Crane's public image as a thumbnail in the regular List view through a hidden, read-only URL field. Frappe does not allow `In List View` on an `Attach Image` field. Keep the image upload field hidden on the form.
10. The linked ERPNext Item uses its native image field to mirror the Crane image, including image changes and removal.
11. On a saved Crane, the Create menu starts an Expense, Maintenance record, or Timesheet with the Crane preselected. Sales Invoice creates draft invoices from that Crane's submitted, unbilled Timesheets, one invoice per Assignment because Assignments may have different customers.
12. `arab_erp_theme` owns Expense Entry and Expense Entry Type. Heavy Equipment Rental depends on it, extends its expense records with crane links, and migrates the previous rental Expense Types and amounts into the shared models. Site branding is now owned by HER (decision 15).
13. Expense Entry has optional Crane and Crane Assignment links supplied by Heavy Equipment Rental. Create → Expense on either saved record opens the shared Expense Entry with its source link prefilled.
14. Show Expense Entry Type titles in links, including the Expense Entry child table; keep the type ID as the stored link value.
15. HER owns its premium industrial theme and all branding assets. Keep theme changes within this app, with yellow/graphite/steel light and dark modes, the supplied crane PNG as logo/favicon, and the supplied GIF for native loading states. Keep workspace structure/order, business logic, DocTypes, and permissions unchanged. Do not modify `arab_erp_theme` or Frappe core. Preserve unrelated custom site branding; apply HER defaults through a separate, idempotent presentation-only hook.
16. Rented Cranes require an ERPNext Supplier. Selecting one on a Timesheet shows an editable **Rented** checkbox, checked by default. When checked, require a positive purchase price per selected **Supplier Billing UOM** and create/submit one native Purchase Invoice in the Timesheet submission transaction using normal accounting permissions and the Assignment company currency. The supplier UOM defaults from Settings (Hour initially) and is saved on each Timesheet. Hour quantity is Total Crane Billable Hours, Day counts distinct worked dates, and Month sums each worked date's calendar-month fraction. Invoice conversion to the Item's Hour stock UOM represents actual distinct crane hours. Unchecking skips purchasing and the purchase-price requirement; preserve the user's choice. Owned cranes never purchase. Retain booking and submitted-shift overlap checks. Customer billing follows Assignment terms. Supplier quantities use actual work, never idle dates across the whole Timesheet period. This supersedes fixed-Hour-only and interval-based purchasing; Hour remains the initial default.

17. Create → Payment on a saved Crane or an invoiced, submitted Timesheet opens an unsaved native supplier Payment Entry against an unpaid submitted Purchase Invoice. Choose an invoice when a Crane has several; ERPNext handles bank details, partial payments, and payment submission. Cancel the Purchase Invoice before cancelling its Timesheet; retain the historical link and use a Timesheet amendment for corrected work. Existing submitted Timesheets are not retroactively purchased, and historical master data is retained.

18. Preserve historical submitted Timesheets and Purchase Invoices without repricing or retroactive purchasing. Keep earlier migration patches and hidden Legacy Purchase Terms. The worked-hour migration archives the previous interval-based terms and initializes Rented on existing records. Clear Day/Month purchase rates only on drafts so their old unit prices cannot silently become hourly prices. Repeated migration must preserve the user's subsequent checkbox choice. Amendments use their captured supplier unit and the current worked-quantity purchasing rules.

19. An Expense Entry's selected Crane Driver (Employee) supplies `Employee` Party Type and that employee's ID on each expense debit row of its Journal Entry. This is Journal Entry attribution only: native General Ledger expense accounts retain no party, and cash/bank rows remain unchanged. HER extends the shared Expense Entry and native Journal Entry controllers within this app; ordinary journals keep native party validation. An idempotent patch fills missing attribution on matching submitted historical journals without changing amounts, ledger entries, or conflicting parties.

20. Treasury Transaction moves funds from the selected Mode of Payment's company default account to another Cash or Bank account in the same company currency. Both accounts must be enabled, non-group accounts and different. Saving is draft; submission creates and submits one balanced native Journal Entry with normal accounting permissions. Cancellation reverses that journal through the Treasury Transaction, retains its link, and allows amendment. Direct journal cancellation is blocked while the source is submitted. Foreign-currency transfers are outside this workflow.

21. Crane Rental Profitability reports submitted rental Sales Invoice net item amounts as income, linked supplier Purchase Invoice net item amounts plus rental Expense Entries as expenses, and Net Sales as income minus expenses. Use company currency and document posting dates, exclude invoice taxes, and follow native invoice returns. Deduplicate invoice links shared by Timesheets. Payments and treasury/custody funding are balance-sheet movements, not additional income or costs. Respect source read permissions. Assignment and Crane filters require explicit expense links; do not infer allocation from dates. Demo data is an explicit, repeatable development-site command, never an install/migration hook.

22. Historical submitted expenses without an existing, submitted, same-company Journal Entry must not crash Rental Profitability. Exclude them from posted totals and list their IDs in a visible report warning. Preserve the records and accounting history; reporting must not automatically create or repair journal postings.

23. Heavy Equipment Rental Settings has **Default Selling UOM** and **Default Supplier Billing UOM**, each Hour/Day/Month, initially Hour. Prefill new Timesheets only; existing Assignment selling terms override defaults. The Crane reference price for the selling unit defaults Agreed Rate, and user overrides remain editable. Capture supplier unit per Timesheet so later Settings changes cannot reinterpret saved rates. Migration initializes missing settings and fills missing purchase units from linked historical invoices (Hour when no invoice), preserving invoices, rates, and existing settings.

24. Crane retains dated ownership/operating agreements. Ownership percentages and **remaining balance distribution percentages** are independent, each totaling 100%. Our Company is optional in the partners table; an operator without ownership/residual entitlement is added to settlement results automatically. External operators must be partner Suppliers. The agreement company stays fixed. Account managers configure accounting once; keep these controls in a collapsed section.

25. The user clarified that this rental scenario has **no taxes**; invoice net amount equals Grand Total. New/changed agreements use **Operating First**: allocated Sales Invoice **base Grand Total** (the actual posted invoice total, before payment deductions and independent of rounded total), less the operator's percentage, less posted operating costs, then distribute the remainder. Allocate each invoice Grand Total across all its items in proportion to signed base net item values using deterministic currency rounding; only attributed items contribute to a crane. Signed returns reverse their allocation. Zero-net invoices with non-zero Grand Total require review. Purchase costs retain net item values; posted Expense Entries and attributed journal income/expense rows retain their signed source amounts. Do not count treasury transfers, payments or settlement journals again. The existing Rental Profitability report stays on net sales, so it can differ from contractual settlement results.

26. Stop both saving and submitting a settlement when costs exceed the balance after operating (or a historical carried loss makes the remaining amount negative). Show revenue, operating share, remaining balance, costs, historical loss and shortfall. Never post a new loss settlement, carry a new deficit forward, or charge negative shares. Exactly zero remaining balance is allowed; the operating share is still due. A supplier who is also the operator receives operating plus residual amounts in one payable. Our Company's operating/residual share is retained without an extra journal. Native Journal Entries post external positive totals; Payment Entries support partial/full settlement.

27. Keep consecutive period closure, locks, immutable agreement/source/share snapshots, permission checks, closed-source guards and reverse-order cancellation. New terms require a later effective date after the latest submitted settlement. Change Agreement switches legacy terms to Operating First. Migration marks existing agreements as Legacy Net Profit without changing their history or original submitted amounts/snapshots; add display breakdowns for historical shares only. Historical net-revenue versions remain applicable to their own dates. Recover existing carried losses under legacy terms before switching; never silently erase them. Explicit demo commands run on a development site only and never from migration.

28. Crane Profit Settlement is the period calculation/approval document. Submission creates the native Journal Entry that recognizes external owner/partner entitlements; it does not pay them. Native Payment Entry records the later cash/bank payment. Describe this distinction plainly to users. The reviewed no-tax example invoices 100,000, deducts 10,000 operating and 20,000 costs, posts 70,000 external entitlements and retains 10,000 for our company. With the demo expense-allocation account, its native accounting result is also 10,000 (12,000 after the operating-rate change).

29. **Superseded by the 2026-11-12 external-owner rule below.** When Our Company operates a crane and is assigned positive ownership under Operated for Owner, normalize the current agreement to Shared Ownership instead of rejecting it. Apply this in the form and server, preserving operating/ownership/residual percentages. Zero-ownership operating-for-owner agreements stay valid, including an agreed residual share. Keep normal effective-date checks, permissions and immutable historical versions; do not migrate saved classifications or posted amounts.

30. The 2026-11-06 treasury workbook request supersedes the old demo data: after a complete site/database/files backup and explicit user confirmation, reset the development company's transactions while retaining master data; import into a **new company using LYD**, rather than changing the EGP company's currency. This is an explicit development command, never a patch/install/migration action. Preserve other-company ledgers and keep an exact deletion audit.
31. For `الخزينه.xlsx`, the user approved zero starting balances, forward-filled missing posting dates, and correcting stored `2026-12-10` / `2026-06-10` to `2026-10-12` / `2026-10-06` wherever present; leave every other date unchanged. Preserve original row order, names, category spellings and descriptions, including the separate DS-13 T35/T36/T37 labels. Do not infer crane attribution. Operating costs use shared Expense Entries; employee advances and owner personal withdrawals remain balance-sheet transfers. Zero opening balances do not produce fictitious opening Journal Entries.
32. Treasury Transactions additionally accept explicitly designated company-currency custody/advance asset accounts and current liability accounts through Account's **Treasury Balance Type**; ordinary arbitrary asset/liability accounts, Receivable/Payable accounts, foreign currencies, disabled/group accounts and self-transfers remain rejected. The **Treasury Workbook** report reads posted native GL entries for one account, checks source permissions, retains workbook row order when selected, and exposes exactly the workbook's seven visible columns plus source links, RTL print and styled Excel export. Native dates/chronological views and opening balances remain available. No historical postings are reclassified by migration.

## Treasury recipient attribution — 2026-11-06

Treasury Transaction has optional paired Party Type/Party fields restricted to registered ERPNext Party Types. Submission copies them to the destination debit row of its native Journal Entry; the source row remains without a party. Attribution stays on the journal, and treasury GL rows retain no party so Cash/Bank posting follows native rules. The persisted source link scopes GL mapping to the matching transaction, company, destination and party, including reposts. Ordinary journals keep native validation. Schema sync adds optional fields without inferring historical parties or rewriting posted transactions.

## Treasury cost centers — 2026-11-06

Treasury Transaction has an optional native Cost Center link, restricted to an enabled leaf in the same company; new submissions copy it to both journal rows. Treasury Workbook filters by the linked Expense Entry/Treasury Transaction Cost Center, since native balance-sheet GL rows may omit it. For ordinary vouchers without a source center, filter the selected account’s actual GL rows only. Apply this before calculating period openings, totals, balances, print and Excel output. Imported transfer categories receive matching company Cost Centers through an idempotent source-only patch; never overwrite an existing assignment or rewrite posted journals/GL.


## Settlement revenue accounts — 2026-11-09

The user requires external partner entitlements under Operating First to reduce
the same Income accounts used by source invoices, rather than an unrelated
Expense/Equity allocation account. Capture source accounts and accounting
dimensions, allocate the external total proportionally to signed source revenue
with deterministic currency rounding, and retain payable/payment separation.
Income journal sources and returns follow the same rule. Legacy Net Profit keeps
its historical allocation treatment. Existing submitted records are not rewritten;
an explicitly corrected unpaid settlement uses native cancellation/amendment.


## 2026-11-10 — Automatic Timesheet settlements and Shareholders

- Supersedes the supplier identity and manual approval parts of decisions 24–28 for new settlements. External partners use native **Shareholder** records, scoped to Company. Existing partner Suppliers are mapped idempotently; native supplier records, dated agreements, submitted journals and payments remain intact. Historical settlement rows retain their original ledger party type while showing the mapped Shareholder. New agreements select Shareholders, including an external operator.
- Each Company receives a separate enabled **Partners** Payable account under liabilities, exposed as Default Crane Partners Account. New crane agreements and Shareholder party accounts default to it. Existing crane trade-payable defaults are replaced on the current master only; explicit alternate accounts and historical postings are preserved.
- Submitting a sharing Crane Timesheet automatically creates one draft settlement, filling Timesheet, Crane and work dates. Invoice creation links the draft invoice. **The user explicitly chose automatic approval/posting after invoice submission**: submit each linked settlement and its native entitlement journal in the invoice transaction, with normal source-read and journal-create/submit permissions. Invalid terms, deficits or posting errors reject the invoice transaction. Payment remains an explicit action.
- Timesheet settlements use their dated work agreement and only their allocated linked invoice revenue. Shared invoice item values are apportioned over submitted Timesheets of that crane by captured billable value; direct purchase costs use linked billable hours. Other posted crane costs/income during overlapping work periods are apportioned by submitted billable hours. Currency rounding is deterministic and source totals are capped across submitted allocations. Preserve the allocation candidates/weights in each source snapshot.
- Resolve any historical carried loss through the retained period workflow before using automatic Timesheet settlements. Period settlements retain consecutive closure and reverse-order cancellation. Do not combine period closure with an already allocated Timesheet source. Prevent new or cancelled overlapping work and changes to captured sources after settlement; reverse settlements first. Historical single-Timesheet links remain explicitly Period basis, preserving their closure behavior. Migration backfills links only; it never posts historical settlements or rewrites native ledgers.
- Settlement shows live entitlement, paid/adjusted amount, outstanding status and linked native Pay Payment Entries, including draft payments. Create → Partner Payment selects the unpaid partner when several remain and opens a draft Pay entry for that partner's remaining balance. ERPNext still handles payment approval, partial payments and cancellation. Payment validation checks the source journal/partner and serializes settlement payment submission.
- **Crane Partner Statement** lists entitlement and payment/adjustment movements with totals. **Crane Partner Summary** groups by Shareholder with totals and 0–30/31–60/61–90/91+ day aging since posting. Both use native Payment Ledger entries as of Report Date and filter Company, optional From Date, Shareholder, Crane, Timesheet and status. Full settlement invoice value is displayed; the totaled Invoice Value is allocated over external entitlements to avoid counting a shared invoice twice. Draft amounts remain separate from posted entitlements. Legacy supplier balances remain payable against their original party/account.

## 2026-11-12 — Remove customer-to-driver invoice payments

Remove Sales Invoice's `crane_drivers`, `customer_pays_drivers_directly` and direct-payment journal link, operator share calculations, customer-to-driver journal posting action/API, associated hooks, child DocType and Settings accounts. Customer invoices follow native ERPNext receivables/payment handling. Keep Timesheet employees, driver hours and independent employee expense attribution. A repeatable pre-model-sync patch archives saved invoice flags, operator rows, journal references and configured accounts in hidden read-only `legacy_driver_payment_data` fields before removing the old metadata. Preserve submitted invoices, journal entries and ledgers without reversal or reposting.

## 2026-11-12 — Prevent accidental zero profit shares for owners

Keep independently agreed ownership and remaining-profit percentages. While they match, ownership edits in the Crane form default Remaining Balance % to the same value; preserve manually different splits and explicitly confirmed zero shares. New or changed agreements reject positive ownership with 0% Remaining Balance unless the row explicitly confirms that the owner receives no remaining profit. Retain confirmation in the dated agreement snapshot. Existing unchanged agreements and submitted settlements are preserved; no migration changes profit splits or posts corrective entitlements. Correct historical terms and settlements through the existing dated-agreement/cancellation/amendment rules.

## 2026-11-12 — Operated for Owner excludes company partner rows

Supersedes decision 29's automatic conversion to Shared Ownership. Operated for Owner requires every `ownership_partners.is_company` to be 0, including zero-ownership rows. The form unchecks company rows when selecting this type, disables the checkbox and defaults new agreements to an external owner. Server validation rejects company rows without changing the selected ownership type. Our Company's operating share remains separate and is added to settlement results automatically; use Shared Ownership to give the company partner ownership or residual entitlement. Preserve dated agreement snapshots, posted settlements and normal effective-date controls; no bulk data changes.

## 2026-11-12 — Expense service periods and Assignment attribution

Expense Entry's optional service dates identify rental work independently of posting date. Assignment-linked expenses default to that Crane's booked period and allocate only among that Assignment's overlapping submitted Timesheets by distinct billable hours. Crane-only dated expenses allocate across overlapping work; undated/unassigned crane expenses retain posting-date behavior. Period settlements use deterministic calendar-day proration. Validate paired/ordered dates, Crane membership and company, and reject periods outside the selected booking. Capture source windows, Assignment, allocation candidates/weights; exclude linked expense journals to avoid counting the cost twice. Freeze captured allocations and block late cost postings to closed work until settlements are cancelled. Preserve existing submitted snapshots, accounting dates and ledgers. This refines the posting-date expense allocation in the 2026-11-10 automatic-settlement decision; native accounting/report posting-date behavior stays unchanged. No automatic native Cost Center creation or historical entitlement reposting.

## 2026-11-12 — Assignment pricing defaults and Timesheet crane selection

Show Rental Rate and Rental Rate Unit in the Assigned Crane grid. Default new rows to Settings Default Selling UOM and the matching Crane reference price, with editable manual rates and protection against pending/stale form responses. Server defaults missing terms on new rows only; saved agreements are never repriced by changed settings/master prices. Missing reference prices still require a positive agreed rate. Create → New Timesheet selects the sole distinct active crane automatically or prompts for one of the Assignment's active cranes; require saving Assignment edits first. Keep existing booking/billing validation. New Timesheets opened through this action default Period Start/End, Rental Rate and Rental Rate Unit from the selected booking; periods stay editable and linked Assignment selling terms retain precedence; choose a rental period when that crane has multiple active booking rows.

## 2026-11-12 — Assignment terms in Timesheet Entries

Display Rental Rate and Rental Rate Unit on each Timesheet Entry, sourced from the single Assignment booking matching the Timesheet crane and shift dates. They are read-only agreed terms, populated while editing drafts and enforced when saving/submitting. Replace the visible hourly-only price column with these fields; retain its stored values internally and keep existing Hour/Day/Month billing and informational driver-amount calculations. Submitted history is not repriced or backfilled from potentially changed master data; new fields populate on new/draft work. This corrects the earlier header-only interpretation of the user's request.

## 2026-11-12 — Editable actual operating hours

Timesheet Entry Worked Hours is editable and authoritative for operating/hourly billing totals, including zero for downtime. Saving or changing shift clock times must not overwrite an entered value or cap it to the scheduled duration. Omitted legacy/API values initialize once from the shift; generated day rows start with Settings day-shift hours. Driver summaries and line amounts use entered hours. To avoid billing simultaneous operators twice, overlap calculations spread each row's entered hours evenly over its scheduled window and use the highest simultaneous operating fraction. Clock windows still validate bookings, dates and submitted-work overlap. Day/Month billing still counts worked dates/calendar fractions; zero-hour rows do not count as worked days. Historical recorded hours and submitted accounting remain intact.

## 2026-11-12 — Editable Driver selector in the shift grid

Show the editable Employee Link as Driver (Employee) in Timesheet Entries instead of the read-only fetched Driver Name. Keep the cached driver name hidden for driver summaries and historical display data. Individual draft rows retain independent drivers; changing a row's Employee refreshes its name and driver-hours summary. Native submitted-document protections remain in place.

## 2026-11-12 — Assignment-filtered expense cranes and inline expense rows

Filter Expense Entry's Crane Link using a permission-checked Assignment query, listing only its distinct active booked cranes. With no Assignment, retain normal Crane selection. On an Assignment change, clear an incompatible Crane (or select its sole available Crane); retain server membership validation. Enable the shared Expense Entry Detail editable grid through HER-owned Property Setters and explicitly size Type/Account/Amount columns. Type and Amount edit inline; Account remains auto-derived from Type. Do not modify arab_erp_theme source, submitted accounting or existing expense data.

## 2026-11-13 — Read-only expense service dates

Expense Entry Service From Date and Service To Date remain visible but read-only. Keep their existing automatic Assignment-booking defaults and saved values; changing field editability does not change settlement allocation, posting dates or historical accounting.

## 2026-11-13 — Assignment Connections

Use Frappe's native Connections tab/dashboard on Crane Assignment for its assigned Cranes, Customer, linked Crane Timesheets and Expense Entries. Map Timesheets through `assignment` and expenses through `crane_assignment`; use native internal links for the Customer and assigned-crane child rows. Invoice/settlement links remain available through the Timesheet Connections. Preserve native document permissions and existing links without data migration.

## 2026-11-13 — Assignment form layout

Keep Assigned Cranes in its own full-width section within Assignment Details, removing the separate Assigned Cranes tab. Retain the native Connections tab and all table data and behavior.

## 2026-11-13 — Shared rental-work selector for maintenance and expenses

Choose Crane and work period, then use Choose Rental Work to explicitly select an overlapping Assignment or non-cancelled Timesheet (draft/submitted). Require a selection on new or changed work attribution when an active booking matches; otherwise allow Crane-only records. Active means a non-cancelled Assigned Crane booking overlapping the work dates, not today's date. A Timesheet fills its Assignment and targets the expense to that Timesheet only. Assignment-level costs retain shared-work allocation. Validate source read permissions, Crane, company, dates and link consistency server-side. Preserve unchanged historical records and submitted sources.

Maintenance uses actual dates when available, otherwise planned dates (today when omitted). Its generated Expense Entry carries both rental links; linked financial attribution is locked after expense creation. Expense matching initially uses Posting Date, while the selector can choose an earlier work period without changing Posting Date. Service From/To stay read-only and are set from the selected work/window; Timesheet-specific service dates must fit the Timesheet. Native Assignment and Timesheet Connections expose directly linked maintenance and expenses. The selector manages read-only job-link displays to prevent conflicting manual links. This extends the earlier Assignment-only expense filtering and required-work attribution now takes precedence over freely leaving matching work unassigned.

## 2026-11-13 — Inline rental links and actual maintenance dates only

Supersedes the modal Choose Rental Work flow. Show editable Assignment and Timesheet links directly in Maintenance and Expense Entry, with filtered native searches and conditional required markers. Require Assignment when booked work matches and Timesheet when that Assignment has matching non-cancelled Timesheets; preserve Crane-only cases when nothing matches. Validate these requirements server-side for new/changed attribution and submission/completion transitions. A selected Timesheet fills Assignment and expense service dates. Expense Assignment search allows earlier bookings for late-posted costs; selecting one defaults its service dates, while Posting Date remains unchanged and service fields remain read-only.

Remove maintenance Planned Start/End Date fields from the form and active calendar/query code. Matching uses Actual Start/End (today if omitted). An idempotent post-sync patch archives old planned values in hidden Legacy Planned Dates without rewriting actual dates, posted costs or timestamps. Existing unchanged historical records remain preserved. Assignment-level costs entered before Timesheets exist retain their original shared-work behavior; newly entered costs must select a matching Timesheet once one exists.

## 2026-11-13 — Optional rental links with unique start-date defaults

Supersedes the mandatory-link rules above for Crane Maintenance and Expense Entry (user confirmed these two forms). Both Assignment and Timesheet are optional and editable on draft/open records. Selecting Crane and Actual Start Date (maintenance) or Posting Date (expense) looks up that single date, independent of the period end, and defaults uniquely matching links. Multiple Timesheets may share a date; never arbitrarily select one. Preserve valid manual selections and protect edits during pending lookups. Manual clearing and ordinary refresh do not reapply defaults. New prefilled forms may initialize defaults once. Server validation permits blank links while still checking explicitly selected Crane/company/work-period consistency and existing accounting locks. Service dates continue to derive from selected rental work; historical submitted records are not relinked.

## 2026-11-13 — Owned Crane profit-sharing checkbox visibility

Hide Enable Profit Sharing when Ownership Type is Owned (and retain the existing Rented exclusion). This is a form visibility rule only; preserve saved agreement flags, dated terms and posted settlements.

## 2026-11-13 — Confirmed rental cancellation

- Cancellation follows business dependencies: Timesheet → invoices → Profit Settlements. Cancelling an invoice preserves submitted Timesheets; cancelling a settlement preserves invoices and Timesheets. A settlement always reverses its own generated entitlement journal. Historical backlinks never expand the cancellation scope.
- Preview each affected document once and require confirmation. Recompute the scope before execution, enforce normal cancellation permissions/payment/closed-period guards, and roll back the complete operation on any failure. Existing paid entitlements require normal payment cancellation or unreconciliation first.

## 2026-11-17 — Timesheet cancellation includes linked costs

Native/API Timesheet cancellation now resolves the existing directed cancellation plan on the server before checking invoice status. It reverses linked payments, settlements, sales/purchase invoices, consolidated expenses and directly attributed expenses; payroll remains controlled by Timesheet on_cancel. Cancellation retains native permissions and accounting locks. Consolidated Expense’s CPS link is a historical backlink, matching the Timesheet backlink exemption when reopening a settlement.
