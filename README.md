# Heavy Equipment Rental

Crane rentals for Frappe/ERPNext. Install `arab_erp_theme` first for the shared expense models. HER supplies its own industrial theme and branding. The **Crane Operations** workspace starts with a **Crane Assignment** or a **Crane Timesheet**. ERPNext's native Project is independent of this workflow.

## Workflow

### Start with an Assignment

1. Create a Crane Assignment with a customer and location.
2. Add one or more cranes. Give each crane its full agreed rental dates, billing unit (Hour, Day, or Month), and rate. Saving the Assignment books those dates.
3. Create one or more Crane Timesheets for each crane. A Timesheet has one Assignment, one crane, and dated operator shifts. Select an optional default Driver (ERPNext Employee) to fill new shifts, then change individual rows as needed. The form shows each driver's name and total shift hours below Operator Shifts. Attach a hard copy if available; it remains accessible and can be updated after submission. Record overtime hours within each shift when applicable.
4. Submit Timesheets when work is approved. Use **Generate Sales Invoice** from a submitted Timesheet or its Assignment. Review and submit the resulting draft Sales Invoice in ERPNext.

### Start with a Timesheet

1. Select the crane, customer, location, and period start and end dates. These dates also become the rental dates if a new Assignment is created.
2. The form finds an existing Assignment that covers the work. If several match, choose one.
3. If none matches, Rental Terms defaults the billing unit from Settings and the agreed rate from the selected Crane's reference price for that unit. Review or override these defaults as needed. Saving creates a single-crane Assignment for the Timesheet period and links it in the same transaction.
4. Later Timesheets with the same customer, location, crane, and covered dates reuse that Assignment.

Extend the Assignment explicitly if work continues beyond its booked dates. The Timesheet Connections tab uses Frappe's standard related-document dashboard.

## Billing defaults

Open **Heavy Equipment Rental Settings → Billing Defaults**. Set **Default Selling UOM** and **Default Supplier Billing UOM** to Hour, Day, or Month; both initially default to Hour.

New Timesheets prefill their selling Billing Unit and Supplier Billing UOM from these settings. Selecting a Crane fills its matching reference price into Agreed Rate. Changing the selling unit updates an automatically filled price; manually entered rates remain yours to edit. Set the Crane's Hour/Day/Month reference prices to avoid repeatedly entering selling rates. Purchase prices remain entered separately. An existing Assignment supplies its agreed selling unit/rate and takes precedence over defaults. Settings changes affect new Timesheets; saved purchase units and agreed terms remain unchanged.

## Booking and work rules

- Saved Assignment date ranges determine crane availability. Overlapping bookings for one crane are rejected, including in separate Assignments. There is no manual Released state.
- A Timesheet crane must belong to its Assignment. Customer, location, and each work date must agree with the booked period.
- Timesheets use native Draft, Submitted, and Cancelled states. Work in a submitted Timesheet is the basis for billing. An active Sales Invoice must be cancelled before cancelling its source Timesheet.
- Each shift records an Employee, work times, optional overtime hours, and calculated worked hours. Overlapping operators contribute to operator hours individually, while crane billable hours count the time only once. A submitted crane shift cannot overlap another submitted Timesheet for that crane.
- Hourly billing uses the agreed rate times distinct crane hours. Daily billing charges each worked calendar day once per booked crane period. Monthly billing prorates distinct worked days by the number of days in each month. An active invoice prevents those hours or days from being billed again.
- Crane Maintenance remains an operational, non-submittable record. Select a shared **Expense Entry Type** and Mode of Payment when completing it; the shared **Expense Entry** posts through an ERPNext Journal Entry. The Crane form shows its bookings, Timesheets, Sales Invoices, and expenses.
- Upload the Crane image from its side panel; these images are public and appear as thumbnails in the regular Crane List view. The linked ERPNext Item shows the same image, including later changes and removal. The form stores a license plate and Hour, Day, and Month reference prices in Crane Details. The Item displays the same prices read-only. After saving, Availability shows a compact month calendar with reserved dates; Connections links related documents.
- From a saved Crane's **Create** menu, start an Expense, Maintenance record, or Timesheet with the Crane preselected. **Sales Invoice** creates draft invoices for the Crane's submitted, unbilled Timesheets, grouped by Assignment so each invoice has one customer.
- The shared Expense Entry has optional Crane and Crane Assignment links supplied by this app. **Create → Expense** on a saved Crane or Crane Assignment opens a new Expense Entry with the corresponding link filled in; neither link is required for other expenses.
- Selecting a Crane Driver (Employee) on Expense Entry fills Party Type **Employee** and that employee's ID on its Journal Entry expense debit rows. These identify the expense recipient on the journal; General Ledger expense rows remain without a party under ERPNext's native accounting rules. Migration fills missing parties on matching historical journals without changing posted amounts or ledger balances.

## Rented cranes and supplier payments

1. Set the Crane's Ownership Type to **Rented** and select its ERPNext **Supplier**.
2. Selecting a rented Crane on a Timesheet shows **Rented**, checked by default. The **Supplier Billing UOM** defaults from Settings; review it and enter a positive **Purchase Price** per that unit. Uncheck **Rented** when this Timesheet should not create a supplier invoice; the choice is saved. Prices use the Assignment company currency and remain separate from the customer agreed rate.
3. Submitting with **Rented** checked automatically creates and submits one **Purchase Invoice** for the Crane's linked Item: **UOM = Supplier Billing UOM** and **Rate = the entered Purchase Price per that unit**. Hour uses **Total Crane Billable Hours**, counting overlapping drivers only once. Day counts distinct worked calendar dates; Month sums each worked date's fraction of its calendar month. Idle dates add no purchase quantity. The invoice conversion to the Item's Hour stock UOM represents actual distinct crane hours. For example, 8 worked hours at 250 per hour produces **8 Hour × 250 = 2,000**, regardless of the Timesheet's date span or customer Billing Unit.
4. Users need normal ERPNext Purchase Invoice create and submit permissions. The Item must allow purchases, and standard supplier/company accounting must be configured. Failed invoice posting rolls back Timesheet submission.
5. Use **Create → Payment** on a saved Crane or submitted, invoiced Timesheet. Choose an unpaid invoice if several are available. Review the draft native **Payment Entry**, choose bank/payment details and amount, then save and submit it. ERPNext Payment Entry create permission is required; this action does not submit a payment automatically.

Timesheet periods may overlap when their actual crane shifts do not overlap. Existing Assignment booking and submitted-shift overlap checks still apply. Customer billing continues to follow the Assignment's agreed terms; hourly sales use the same worked crane hours as purchases.

Cancel the Purchase Invoice before cancelling its Timesheet. To correct submitted work, cancel both and amend the Timesheet; its replacement gets a new invoice when **Rented** is checked. Existing submitted Timesheets do not create retroactive Purchase Invoices, and historical invoices keep their original quantities, units, rates, and amounts. Migration archives previous purchase terms; Day/Month purchase prices on existing drafts are cleared so users enter an hourly price before submission. Rented Cranes still require their Supplier on the master record.

## Crane ownership and profit sharing

Crane supports **Shared Ownership**, **Operated for Owner**, and **Operated by
Partner**, with separate ownership and remaining balance percentages. Enter the
operator, operating percentage and dated agreement once. Submitting a sharing
Timesheet creates its settlement; submitting the Sales Invoice approves/posts it
automatically. The settlement takes its allocated Sales Invoice **Grand Total**, deducts
the operating share first, then costs, and distributes the remainder. A deficit
blocks saving/submission with its numerical explanation. Exactly zero remainder
is allowed. External partners use native **Shareholders** and a company-specific
**Partners** Payable account. Native Journal Entries recognize entitlements;
Partner Payment opens a Pay Payment Entry for the selected unpaid partner,
including partial payments. Historical supplier postings remain unchanged.

**Change Agreement** dates new operating, ownership and distribution terms;
submitted snapshots retain their original values. Historical net-profit versions
are preserved by migration. Optional Crane attribution on native invoice items
and journal rows covers other revenue/costs. Rental Profitability retains its
net-sales basis. See [configuration and accounting](docs/PROFIT_SHARING.md) and
[the full numerical development example](docs/OPERATING_FIRST_DEMO.md).

## Treasury transfers

Open **Treasury Transaction** from Desk search or the **Treasury Transactions** shortcut in Crane Operations. Select the Company, Posting Date, and Mode of Payment; its company-specific default account is the source. Choose another Cash or Bank account and enter a positive Amount. Both accounts must be enabled, non-group accounts in the company currency. In addition to Cash/Bank, an Account explicitly designated through **Treasury Balance Type** may represent custody, employee advances (Asset) or current balances (Liability); Receivable/Payable accounts remain excluded. Foreign-currency transfers are not supported.

Select an optional **Cost Center** from enabled, non-group centers in the selected company; it is copied to both Journal Entry rows. Saving keeps a draft. **Submit** automatically creates and submits one native Journal Entry, crediting the source and debiting the destination. The form retains the Journal Entry link; optional reference number/date and description are copied to it. Normal Treasury Transaction and Journal Entry accounting permissions apply. Posting failures roll back the submission.

Optionally select **Party Type** and **Party** to identify the recipient (for example, an Employee, Supplier or Customer). Select both together or leave both blank. They are copied to the destination debit row of the generated Journal Entry. They identify the recipient on the journal only; treasury GL balances retain no party under native accounting rules. Existing submitted transfers and journals are preserved.

Cancel the Treasury Transaction to cancel its Journal Entry and reverse the transfer. Direct cancellation of the linked journal is blocked while its Treasury Transaction is submitted. The cancelled record retains the journal link; amend it for a corrected transfer. Existing records are unaffected.

## Treasury workbook and custody statements

Open **Crane Operations → Treasury Workbook** for the seven-column RTL treasury/custody statement, source document links, a company-specific **Cost Center** filter, period opening balance and print/Excel output in the workbook layout. With a Cost Center selected, balances and totals apply to that center only. The report reads posted native General Ledger movements, includes advances/current-account transfers, and opens the latest accessible import without changing user company defaults. See [the LYD workbook reconciliation and audited development reset](docs/TREASURY_WORKBOOK.md). Imports/resets are explicit commands, never migration hooks.

## Rental income and expenses

Open **Crane Operations → Rental Profitability** (or search **Crane Rental Profitability**).
Choose Company and posting-date range; optionally filter by Assignment or Crane. The report
shows Total Income, Total Expenses, and **Net Sales = Income − Expenses**, with linked
documents and the actual cash/custody source account for expenses.

Income is submitted Sales Invoice item net amounts linked through submitted rental Timesheets.
Costs are linked submitted Purchase Invoice item net amounts plus submitted rental Expense
Entries. Native invoice returns reduce the corresponding amounts. Drafts, cancelled records,
payments, and treasury transfers are excluded. Invoice values exclude taxes and use company
currency. This is recorded rental margin, not cash receipts or a complete company profit and loss.
Unbilled Timesheets are excluded. An Assignment filter requires an explicit Assignment link on
expenses; a Crane filter requires an explicit Crane link. Users need read access to the rental and
accounting source documents; the report does not grant accounting permissions.
Historical expenses with a missing, draft, cancelled, or wrong-company Journal Entry are
excluded with a visible warning listing their IDs. Review those records before relying on totals;
opening the report never changes or reposts them.

See [the simulated rental cycle](docs/SIMULATED_RENTAL.md) for the development-site example
and the explicit, repeatable demo command. Demo records are never created by migration.

## Existing records

On migration, existing Crane Project or native Project references are used once to populate Assignment customer, company, and location, and to link historical Timesheets to Assignments. A legacy project name becomes the location when no separate location existed. Review those locations and any old overlapping bookings or zero rates before invoicing historical work. The custom Crane Project DocType is removed after migration; ERPNext's native Project DocType is unchanged. Existing signed Timesheet uploads move to the new hard-copy attachment field. Previous Year reference prices move to a hidden legacy field on Crane.

Existing rental Expense Types migrate to `arab_erp_theme` Expense Entry Types, and existing Expense Entry amounts move into the shared expense rows. Earlier migrations removed the rental-owned Expense Type and Expense Entry DocTypes and handed branding to the base theme. HER now supplies its own theme and branding again; unrelated custom site branding is preserved.

A database backup is recommended before migrating a site. Run:

```bash
bench --site YOUR_SITE migrate
```

## Calendar

`/rental-calendar` and `/rental-calendar/timeline` show bookings, Timesheet work, and maintenance. The timeline can group by Assignment or crane. After changing `frontend/src`, rebuild the tracked assets:

```bash
cd frontend
npm ci
npm run build
```

## Tests

With tests enabled on a development site:

```bash
bench --site YOUR_SITE run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.crane_assignment.test_rental_workflow
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
