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
3. If none matches, enter the billing unit and rate in the new rental terms section. Saving creates a single-crane Assignment for the Timesheet period and links it in the same transaction.
4. Later Timesheets with the same customer, location, crane, and covered dates reuse that Assignment.

Extend the Assignment explicitly if work continues beyond its booked dates. The Timesheet Connections tab uses Frappe's standard related-document dashboard.

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
