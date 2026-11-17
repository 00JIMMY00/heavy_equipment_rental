# Heavy Equipment Rental

Crane rentals for Frappe/ERPNext. Install `arab_erp_theme` first for the shared expense models. HER supplies its own industrial theme and branding. Start from **Crane Operations → Cranes → Operations**. The Crane is the main hub for bookings, work, repairs, Assets and owner settlements. Rental Contract-first and Timesheet-first entry remain available. ERPNext's native Project is independent of this workflow.

On every site with HER installed, opening `/`, `/app`, or `/app/` takes users to Crane Operations. Frappe sends guests through sign-in and retains direct document and report links.

## Native workflow redesign

Read the [illustrated user guide](docs/USER_GUIDE.md) for setup, daily operation, repair choices and complete accounting examples.

See [the complete operational and accounting design](docs/NATIVE_CRANE_WORKFLOW.md). New cranes share a rental-service Item and link their physical native Asset separately. Ownership determines Asset recognition: Owned records the full company cost; shared equipment records only our interest; zero company ownership has no Asset. Repairs use native Material Issue, service Purchase Invoice, Asset Repair or owner Sales Invoice according to their cost treatment; only qualifying improvements increase Asset value. New agreements restore automatic source-revenue settlements on Sales Invoice submission, using Invoice Grand Total and excluding depreciation from the distribution pool. Historical agreements and posted ledgers are preserved.

## Workflow

### Start with an Rental Contract

1. Create a Rental Contract with a customer and location.
2. Add one or more cranes. Billing unit defaults from HER Settings and rate from the Crane reference price; both are visible in the table and editable. Give each crane its full agreed rental dates. Saving the Rental Contract books those dates.
3. Use Create → New Timesheet and choose a crane when the Rental Contract has several active cranes. Create one or more Crane Timesheets for each crane. A Timesheet has one Rental Contract, one crane, and dated operator shifts. Select an optional default Driver (ERPNext Employee) to fill new shifts, then change individual rows as needed. Driver Payroll summarizes the drivers' work below Operator Shifts. Attach a hard copy if available and update it after submission when needed. Record overtime hours within each shift when applicable.
4. Submit Timesheets when work is approved. Use **Generate Sales Invoice** from a submitted Timesheet or its Rental Contract. Review and submit the resulting draft Sales Invoice in ERPNext.

Customer payments use ERPNext's normal invoice/payment workflow. Sales Invoices do not allocate amounts to drivers or record customer-to-driver payments. Driver names and hours remain on Timesheets. Migration preserves previously saved direct-payment details in a hidden legacy archive and leaves posted invoices/journals unchanged.

### Start with a Timesheet

1. Select the crane, customer, location, and period start and end dates. These dates also become the rental dates if a new Rental Contract is created.
2. The form finds an existing Rental Contract that covers the work. If several match, choose one.
3. If none matches, Rental Terms defaults the billing unit from Settings and the agreed rate from the selected Crane's reference price for that unit. Review or override these defaults as needed. Saving creates a single-crane Rental Contract for the Timesheet period and links it in the same transaction.
4. Later Timesheets with the same customer, location, crane, and covered dates reuse that Rental Contract.

On a draft Timesheet, use **Entries → Operator Shifts → Fill Table** to add a shift for each missing date between **Period Start** and **Period End**. New rows use the configured Day Shift defaults and the optional **Default Driver** from **Timesheet Details**. If any shift's Work Date is outside the period, the button shows how many rows it will remove and asks for confirmation before filling. Shifts within the period keep their entered values, and saving the draft applies the changes.

Extend the Rental Contract explicitly if work continues beyond its booked dates. The Timesheet Connections tab uses Frappe's standard related-document dashboard.

### Driver payroll

1. In **Heavy Equipment Rental Settings → Driver Payroll**, add a row for the rental company. Choose the **Payroll Expense Type** for the salary expense account and the **Payroll Mode of Payment** whose company default account funds the payment.
2. Add or select drivers in **Operator Shifts**. **Driver Payroll** shows the worked quantity, **Price / Hour**, **Price / Day**, or **Price / Month** according to the billing unit, and **Payroll Amount**. Enter a price to calculate the amount, or enter an amount to calculate the price. The last field you edit stays fixed when shifts change. A fixed amount can be entered before there is any worked quantity. Its price appears once work is recorded. Leave the price and amount blank or zero to skip a driver.
3. Open a row with the pencil icon to see its payroll unit, worked hours, **Mode of Payment**, and Expense Entry link. The payment mode defaults from the company’s payroll settings and can be changed per driver. Submit the Timesheet to post one **Expense Entry** and Journal Entry per paid driver using the row’s payment mode and the submission date.

Hourly quantity sums actual hours per driver. Daily quantity counts distinct worked dates per driver. Monthly quantity prorates those dates by the length of their calendar months. Use the Timesheet's **Cancel** action to reverse its payroll expenses. Amend the Timesheet to correct amounts and post replacement entries.

## Consolidated expenses

Use **Crane Operations → مصروف مجمع (Grouped Expense)** to enter dated expenses for one rental Timesheet. Download/upload the Excel template, edit type/payment overrides with the row pencil, and Submit to post the batch. Configure company defaults under **HER Settings → Grouped Expenses**. [Usage and accounting](docs/CONSOLIDATED_EXPENSES.md).

## Billing defaults

Open **Heavy Equipment Rental Settings → Billing Defaults**. Set **Default Selling UOM** and **Default Supplier Billing UOM** to Hour, Day, or Month; both initially default to Hour.

Set **Crane → Default Selling UOM** to Hour, Day, or Month, and enter its matching reference prices. The Crane default initially comes from HER Settings. New Rental Contract rows show that unit and price; both can be edited. Timesheets visibly inherit their Rental Contract terms, or the Crane defaults when starting a new rental. You can change **Billing unit** and **Agreed rate** on a draft Timesheet; saving retains the choice without changing the Rental Contract. Its submitted terms determine sales billing. Master default changes do not reprice saved work.

Generated Sales Invoice items display the selected UOM, worked quantity and rate: for example, **3 Day × 1,500**, rather than **1 Hour × 4,500**. Monthly quantities are fractions of calendar months. Draft invoice rows remain editable using ERPNext's normal controls. Hour stock quantities track actual crane work; they do not replace the invoice billing unit. Flat-rate Timesheets for the same booked crane/day must use matching terms to avoid double billing.

Supplier Billing UOM still defaults separately from Settings and remains editable. Purchase prices are entered separately.

## Booking and work rules

- Saved Rental Contract date ranges determine crane availability. Overlapping bookings for one crane are rejected, including in separate Assignments. There is no manual Released state.
- A Timesheet crane must belong to its Rental Contract. Customer, location, and each work date must agree with the booked period.
- Timesheets use native Draft, Submitted, and Cancelled states. Work in a submitted Timesheet is the basis for billing. An active Sales Invoice must be cancelled before cancelling its source Timesheet.
- Each shift records an Employee, work times, optional overtime hours, and editable actual worked hours excluding downtime. Entered hours are retained when clock times change. Overlapping operators contribute to operator hours individually, while crane billable hours count the time only once. A submitted crane shift cannot overlap another submitted Timesheet for that crane.
- Hourly billing uses the agreed rate times entered crane operating hours, deduplicating simultaneous operators over their scheduled windows. Daily billing charges each worked calendar day once per booked crane period. Monthly billing prorates distinct worked days by the number of days in each month. An active invoice prevents those hours or days from being billed again.
- Crane Maintenance uses native Submit → Cancel → Amend. Draft repairs hold dates, items and payment details; Submit creates their native invoices, stock movements, Asset Repair and payments automatically for the selected source/purpose. Cancel previews and reverses the related documents atomically; Amend creates an editable replacement that posts fresh entries. Cash Expense creates its Expense Entry on submission. Existing posted repairs are migrated without reposting. See [repair workflow](docs/NATIVE_CRANE_WORKFLOW.md#repairs-including-company-owned-shared-and-external-cranes).
- Upload the Crane image from its side panel; these images are public and appear as thumbnails in the regular Crane List view. Legacy per-crane Items retain their image mirror; the shared service Item is not overwritten by individual cranes. The form stores a license plate and Hour, Day, and Month reference prices in Crane Details. Legacy per-crane Items display the same prices read-only. After saving, Availability shows a compact month calendar with reserved dates; Connections links related documents.
- From a saved Crane's **Create** menu, start an Expense, Maintenance record, or Timesheet with the Crane preselected. **Sales Invoice** creates draft invoices for the Crane's submitted, unbilled Timesheets, grouped by Rental Contract so each invoice has one customer.
- The shared Expense Entry has optional Crane and Rental Contract links supplied by this app. **Create → Expense** on a saved Crane or Rental Contract opens a new Expense Entry with the corresponding link filled in; neither link is required for other expenses.
- Selecting a Crane Driver (Employee) on Expense Entry fills Party Type **Employee** and that employee's ID on its Journal Entry expense debit rows. These identify the expense recipient on the journal; General Ledger expense rows remain without a party under ERPNext's native accounting rules. Migration fills missing parties on matching historical journals without changing posted amounts or ledger balances.

## Rented cranes and supplier payments

1. Set the Crane's Ownership Type to **Rented** and select its ERPNext **Supplier**.
2. Selecting a rented Crane on a Timesheet shows **Rented**, checked by default. The **Supplier Billing UOM** defaults from Settings; review it and enter a positive **Purchase Price** per that unit. Uncheck **Rented** when this Timesheet should not create a supplier invoice; the choice is saved. Prices use the Rental Contract company currency and remain separate from the customer agreed rate.
3. Submitting with **Rented** checked automatically creates and submits one **Purchase Invoice** for the Crane's linked Item: **UOM = Supplier Billing UOM** and **Rate = the entered Purchase Price per that unit**. Hour uses **Total Crane Billable Hours**, counting overlapping drivers only once. Day counts distinct worked calendar dates; Month sums each worked date's fraction of its calendar month. Idle dates add no purchase quantity. The invoice conversion to the Item's Hour stock UOM represents actual distinct crane hours. For example, 8 worked hours at 250 per hour produces **8 Hour × 250 = 2,000**, regardless of the Timesheet's date span or customer Billing Unit.
4. Users need normal ERPNext Purchase Invoice create and submit permissions. The Item must allow purchases, and standard supplier/company accounting must be configured. Failed invoice posting rolls back Timesheet submission.
5. Use **Create → Payment** on a saved Crane or submitted, invoiced Timesheet. Choose an unpaid invoice if several are available. Review the draft native **Payment Entry**, choose bank/payment details and amount, then save and submit it. ERPNext Payment Entry create permission is required; this action does not submit a payment automatically.

Timesheet periods may overlap when their actual crane shifts do not overlap. Existing Rental Contract booking and submitted-shift overlap checks still apply. Customer billing continues to follow the Rental Contract's agreed terms; hourly sales use the same worked crane hours as purchases.

Cancel the Purchase Invoice before cancelling its Timesheet. To correct submitted work, cancel both and amend the Timesheet; its replacement gets a new invoice when **Rented** is checked. Existing submitted Timesheets do not create retroactive Purchase Invoices, and historical invoices keep their original quantities, units, rates, and amounts. Migration archives previous purchase terms; Day/Month purchase prices on existing drafts are cleared so users enter an hourly price before submission. Rented Cranes still require their Supplier on the master record.

## Crane fixed assets

[شرح عربي مختصر لمنطق الأصول المشتركة](docs/ASSETS_AR.md).

Owned cranes record the full Company Asset; shared cranes record only the Company's positive ownership interest. The basis is derived automatically and is read-only. Zero Company ownership, rented cranes and equipment operated solely for others have no Asset link or creation action. `ownership_partners` remains the ownership/profit agreement table.

Link one quantity-1 native Asset in the correct Company, using a fixed-asset Item separate from the rental service Item. For a 1,000,000 crane with 40% Company ownership, the native Company Asset cost is 400,000. Its amounts already represent our interest and are never multiplied by ownership again. Enter recognized amounts through native acquisition/opening/improvement documents; changing a percentage does not automatically resize posted Assets.

The financial panel shows only Company cost, capitalized improvements and book value using the Company default Finance Book. Other owners' Asset values are not displayed. Normal permissions, unique links and native Asset validation remain enforced. Linking posts no accounting entries. Migration archives obsolete whole/shared and zero-ownership/custody links for correction, preserving original Assets and ledgers. Native depreciation remains governed by Asset settings and the settlement policy.

## Crane ownership and profit sharing

**Crane Operations → Crane Profit Distribution** shows company operating/residual shares, partner entitlements, expense burden, source documents and payment balances, with five views and company/Crane/partner/date/status filters. [دليل التقرير الشامل](docs/PROFIT_DISTRIBUTION_REPORT.md).

[تجربة استعادة التوزيع التلقائي على ونش موجود](docs/RESTORED_SETTLEMENT_AR.md).

Crane supports **Shared Ownership**, **Operated for Owner**, and **Operated by
Partner**, with separate ownership and remaining balance percentages. Enter the
operator, operating fees and current owner/profit shares. Submitting a sharing
Timesheet creates a draft settlement. Record all costs before submitting the Sales Invoice: its submission automatically posts partner entitlements against the source revenue accounts. The settlement takes its agreed invoice Grand Total, deducts
the operating share first, then costs, and distributes the remainder. A deficit blocks submission with its numerical explanation; review-mode drafts can retain the shortfall. Exactly zero remainder
is allowed. External partners use native **Shareholders** and a company-specific
**Partners** Payable account. Native Journal Entries recognize entitlements;
Partner Payment opens a Pay Payment Entry for the selected unpaid partner,
including partial payments. Historical supplier postings remain unchanged.

Edit **Owners & Profit Shares** and **Operating Fees**, then Save. No effective date is required; current terms apply when draft settlements are recalculated. Submitted snapshots retain their original values. Historical net-profit versions
are preserved by migration. Optional Crane attribution on native invoice items
and journal rows covers other revenue/costs. Rental Profitability retains its
net-sales basis. See [configuration and accounting](docs/PROFIT_SHARING.md) and
[the full numerical development example](docs/OPERATING_FIRST_DEMO.md).

Maintenance and expenses show editable **Rental Contract** and **Crane Timesheet** links directly. Choose Crane and start date to default uniquely matching rental links. Both links are optional and editable; ambiguous Timesheets remain for manual selection. Maintenance uses Actual Start/End dates only. A Timesheet fills its Rental Contract automatically; Crane-only records are allowed when no work matches. Maintenance carries its selection into the generated expense.

Rental expenses display **Crane**, **Rental Contract**, optional **Crane Timesheet**, and read-only **Service From/To Date**. The Rental Contract defaults its Crane booking period; select a Timesheet to use its work period. Settlement uses that work attribution even if the expense is posted later, allocating it once among eligible submitted Timesheets by billable hours. Enter all costs before approving the settlement. Under historical automatic agreements, costs must be complete before invoice submission. Reopen affected settlements before adding costs for closed work. Posted accounting dates and existing submitted settlements are preserved. See [expense allocation rules](docs/PROFIT_SHARING.md).

## Treasury transfers

Open **Treasury Transaction** from Desk search or the **Treasury Transactions** shortcut in Crane Operations. Select the Company, Posting Date, and Mode of Payment; its company-specific default account is the source. Choose another Cash or Bank account and enter a positive Amount. Both accounts must be enabled, non-group accounts in the company currency. In addition to Cash/Bank, an Account explicitly designated through **Treasury Balance Type** may represent custody, employee advances (Asset) or current balances (Liability); Receivable/Payable accounts remain excluded. Foreign-currency transfers are not supported.

Select an optional **Cost Center** from enabled, non-group centers in the selected company; it is copied to both Journal Entry rows. Saving keeps a draft. **Submit** automatically creates and submits one native Journal Entry, crediting the source and debiting the destination. The form retains the Journal Entry link; optional reference number/date and description are copied to it. Normal Treasury Transaction and Journal Entry accounting permissions apply. Posting failures roll back the submission.

Optionally select **Party Type** and **Party** to identify the recipient (for example, an Employee, Supplier or Customer). Select both together or leave both blank. They are copied to the destination debit row of the generated Journal Entry. They identify the recipient on the journal only; treasury GL balances retain no party under native accounting rules. Existing submitted transfers and journals are preserved.

Cancel the Treasury Transaction to cancel its Journal Entry and reverse the transfer. Direct cancellation of the linked journal is blocked while its Treasury Transaction is submitted. The cancelled record retains the journal link; amend it for a corrected transfer. Existing records are unaffected.

## Treasury workbook and custody statements

Open **Crane Operations → Treasury Workbook** for the seven-column RTL treasury/custody statement, source document links, a company-specific **Cost Center** filter, period opening balance and print/Excel output in the workbook layout. With a Cost Center selected, balances and totals apply to that center only. The report reads posted native General Ledger movements, includes advances/current-account transfers, and opens the latest accessible import without changing user company defaults. See [the LYD workbook reconciliation and audited development reset](docs/TREASURY_WORKBOOK.md). Imports/resets are explicit commands, never migration hooks.

## Rental income and expenses

Open **Crane Operations → Rental Profitability** (or search **Crane Rental Profitability**).
Choose Company and posting-date range; optionally filter by Rental Contract or Crane. The report
shows Total Income, Total Expenses, and **Net Sales = Income − Expenses**, with linked
documents and the actual cash/custody source account for expenses.

Income is submitted Sales Invoice item net amounts linked through submitted rental Timesheets.
Costs include linked supplier hire invoices, rental Expense Entries, native repair stock/service postings and attributed depreciation/other journals. Native invoice returns reduce the corresponding amounts. Drafts, cancelled records,
payments, and treasury transfers are excluded. Invoice values exclude taxes and use company
currency. This is recorded rental margin, not cash receipts or a complete company profit and loss.
Unbilled Timesheets are excluded. An Rental Contract filter requires an explicit Rental Contract link on
expenses; a Crane filter requires an explicit Crane link. Users need read access to the rental and
accounting source documents; the report does not grant accounting permissions.
Historical expenses with a missing, draft, cancelled, or wrong-company Journal Entry are
excluded with a visible warning listing their IDs. Review those records before relying on totals;
opening the report never changes or reposts them.

See [the simulated rental cycle](docs/SIMULATED_RENTAL.md) for the development-site example
and the explicit, repeatable demo command. Demo records are never created by migration.

## Existing records

On migration, existing Crane Project or native Project references are used once to populate Rental Contract customer, company, and location, and to link historical Timesheets to Assignments. A legacy project name becomes the location when no separate location existed. Review those locations and any old overlapping bookings or zero rates before invoicing historical work. The custom Crane Project DocType is removed after migration; ERPNext's native Project DocType is unchanged. Existing signed Timesheet uploads move to the new hard-copy attachment field. Previous Year reference prices move to a hidden legacy field on Crane.

Existing rental Expense Types migrate to `arab_erp_theme` Expense Entry Types, and existing Expense Entry amounts move into the shared expense rows. Earlier migrations removed the rental-owned Expense Type and Expense Entry DocTypes and handed branding to the base theme. HER now supplies its own theme and branding again; unrelated custom site branding is preserved.

A database backup is recommended before migrating a site. Run:

```bash
bench --site YOUR_SITE migrate
```

## Calendar

`/rental-calendar` and `/rental-calendar/timeline` show bookings, Timesheet work, and maintenance. The timeline can group by Rental Contract or crane. After changing `frontend/src`, rebuild the tracked assets:

```bash
cd frontend
npm ci
npm run build
```

## Tests

With tests enabled on a development site:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.rental_contract.test_rental_workflow
```

Purchasing integration tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.crane_timesheet.test_crane_timesheet
```

Employee expense accounting tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.test_expenses
```

Treasury accounting integration tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.treasury_transaction.test_treasury_transaction
```

Rental report and simulated cycle integration tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.report.crane_rental_profitability.test_crane_rental_profitability
```

Ownership, profit settlements and partner accounting integration tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.test_crane_profit_settlement
```

The report and settlement tests use the development fixture company `cranes company` and roll back their records.

Crane/Asset accounting integration tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.crane.test_crane
```

## Industrial theme

All theme files live in this app; no Frappe, ERPNext, or `arab_erp_theme` source changes are required. The CSS in `heavy_equipment_rental/public/css/industrial_*.css` styles Desk and login with machinery yellow, graphite, neutral surfaces, and accessible focus states. `industrial_tokens.css` supplies shared light/dark tokens and deliberately takes precedence over the base theme regardless of installed-app order. Desk keeps Frappe's native theme switcher; the calendar and timeline read the same user's Desk preference, including Automatic mode.

The supplied crane PNG is served as the primary logo and as a multi-size ICO favicon. The original GIF is used for Frappe's native startup splash, blocking-request overlay, and calendar refresh indicator, with a static PNG for reduced-motion users. Native loader timing, nested request counts, and grid editor backdrops remain intact. Branding settings are applied on installation/migration only when they are empty or still use framework/base-theme/HER defaults; unrelated custom branding is retained.

To deploy the theme to an existing site without running rental setup or syncing workspaces:

```bash
cd frontend
npm ci
npm run build
cd ../../..
bench build --app heavy_equipment_rental
bench --site YOUR_SITE execute heavy_equipment_rental.branding.apply_branding
bench --site YOUR_SITE clear-cache
bench --site YOUR_SITE clear-website-cache
```

These are presentation changes; no schema migration is needed. Reload open browser tabs after deployment. See [docs/THEME.md](docs/THEME.md) for maintenance and verification notes.

For deployment details, see [deploy/README.md](deploy/README.md).

## License

MIT


Sharing Timesheets automatically create linked settlements; Sales Invoice submission automatically approves/posts partner entitlements. Partners are native **Shareholders** with a company-specific **Partners** payable default. Use **Crane Operations → Crane Partner Statement / Crane Partner Summary** for movements, totals, invoice values, payment status and aging. Open a settlement's **Create → Partner Payment** to choose an unpaid partner and prepare a native Pay entry. [Current sharing workflow](docs/PROFIT_SHARING.md).

Automatic settlement and Shareholder/report tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.test_partner_settlements
```

Native Asset/repair/stock/owner accounting integration tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.test_native_crane_workflow
```

Comprehensive profit distribution report tests:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.test_distribution_reporting
```

## Customize Crane Operations

Crane Operations groups daily work, billing/treasury, partners, reports and setup into editable native workspace cards. Use **Customize → Save** as Administrator or Workspace Manager to arrange it on your site. Site edits survive later app migrations. See [workspace editing and deployment](docs/WORKSPACE.md).

Rental Contract and Timesheet **Location** is a link to ERPNext **Location**. Select an existing location or create one through the picker when permitted. The Rental Contract location fills into its Timesheets. Existing text locations are preserved as native Location records by migration.
