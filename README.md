# Heavy Equipment Rental

Crane rentals for Frappe/ERPNext. The **Crane Operations** workspace starts with a **Crane Assignment** or a **Crane Timesheet**. ERPNext's native Project is independent of this workflow.

## Workflow

### Start with an Assignment

1. Create a Crane Assignment with a customer and location.
2. Add one or more cranes. Give each crane its full agreed rental dates, billing unit (Hour, Day, or Month), and rate. Saving the Assignment books those dates.
3. Create one or more Crane Timesheets for each crane. A Timesheet has one Assignment, one crane, and dated operator shifts. Operators are ERPNext Employees. Record overtime hours within each shift when applicable.
4. Submit Timesheets when work is approved. Use **Generate Sales Invoice** from a submitted Timesheet or its Assignment. Review and submit the resulting draft Sales Invoice in ERPNext.

### Start with a Timesheet

1. Select the crane, customer, location, and work dates.
2. The form finds an existing Assignment that covers the work. If several match, choose one.
3. If none matches, enter the **full agreed rental period**, billing unit, and rate in the new rental terms section. Saving creates a single-crane Assignment and links the Timesheet in the same transaction.
4. Later Timesheets with the same customer, location, crane, and covered dates reuse that Assignment.

The agreed rental period is never inferred from Timesheet dates. Extend the Assignment explicitly if work continues beyond its booked dates.

## Booking and work rules

- Saved Assignment date ranges determine crane availability. Overlapping bookings for one crane are rejected, including in separate Assignments. There is no manual Released state.
- A Timesheet crane must belong to its Assignment. Customer, location, and each work date must agree with the booked period.
- Timesheets use native Draft, Submitted, and Cancelled states. Work in a submitted Timesheet is the basis for billing. An active Sales Invoice must be cancelled before cancelling its source Timesheet.
- Each shift records an Employee, work times, optional overtime hours, and calculated worked hours. Overlapping operators contribute to operator hours individually, while crane billable hours count the time only once. A submitted crane shift cannot overlap another submitted Timesheet for that crane.
- Hourly billing uses the agreed rate times distinct crane hours. Daily billing charges each worked calendar day once per booked crane period. Monthly billing prorates distinct worked days by the number of days in each month. An active invoice prevents those hours or days from being billed again.
- Crane Maintenance remains an operational, non-submittable record. Expense Entries post through standard ERPNext Journal Entries. The Crane form shows its bookings, Timesheets, Sales Invoices, and expenses.

## Existing records

On migration, existing Crane Project or native Project references are used once to populate Assignment customer, company, and location, and to link historical Timesheets to Assignments. A legacy project name becomes the location when no separate location existed. Review those locations and any old overlapping bookings or zero rates before invoicing historical work. Historical Crane Project records remain read only; new rentals do not use them. ERPNext's native Project DocType is unchanged.

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
