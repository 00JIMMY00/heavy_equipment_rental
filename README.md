# Heavy Equipment Rental

Crane rentals for Frappe/ERPNext. The **Crane Operations** workspace starts with a **Crane Assignment** or a **Crane Timesheet**. ERPNext's native Project is independent of this workflow.

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
- Crane Maintenance remains an operational, non-submittable record. Expense Entries post through standard ERPNext Journal Entries. The Crane form shows its bookings, Timesheets, Sales Invoices, and expenses.
- The Crane form stores an optional image and license plate. Its Hour, Day, and Month reference prices appear in Crane Details. Connections links related rental and operations documents; the availability overview uses today's date.

## Existing records

On migration, existing Crane Project or native Project references are used once to populate Assignment customer, company, and location, and to link historical Timesheets to Assignments. A legacy project name becomes the location when no separate location existed. Review those locations and any old overlapping bookings or zero rates before invoicing historical work. The custom Crane Project DocType is removed after migration; ERPNext's native Project DocType is unchanged. Existing signed Timesheet uploads move to the new hard-copy attachment field. Previous Year reference prices move to a hidden legacy field on Crane.

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

For deployment details, see [deploy/README.md](deploy/README.md).

## License

MIT
