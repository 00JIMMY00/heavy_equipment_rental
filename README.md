# Jimmy Cranes

Crane rental management for Frappe/ERPNext. The Jimmy Cranes workspace uses its own **Crane Project** DocType alongside crane, assignment and timesheet DocTypes. ERPNext Project is independent.

## Workflow

1. Create an **Open Crane Project** and one or more **Crane Assignments**. Each assignment
   is a non-submittable batch containing 100+ **Assigned Crane** child rows.
2. Add proposed cranes and planned dates as **Draft** rows. Drafts do not reserve
   availability. Use **Reserve Selected** to commit the selected cranes.
3. Record actual work in **Crane Timesheet**. Reserved is sufficient: there is no
   Start action or In Progress booking status. Each timesheet has one header crane
   and multiple operator shifts, with native Draft/Submit/Cancel behavior.
4. Use **Release Selected** to record the actual release date. The expected end
   remains unchanged. Use **Cancel Selected** with a date and reason only when no
   work has been recorded, including draft timesheets.
5. Explicitly mark the Crane Project **Completed** or **Cancelled** after all Draft
   and Reserved allocations are resolved and all draft timesheets are submitted
   or removed. Releasing the last crane never closes the Project automatically.

Only child rows have a booking status: **Draft → Reserved → Released**, or
**Draft/Reserved → Cancelled**. Explicit **Undo Reserve**, **Undo Release**, and
**Undo Cancel** actions restore a mistaken action; a correction reason is required.
Undo Cancel restores the recorded previous status. Older cancelled rows without
that history require a choice of Draft or Reserved. Crane
Assignment has no parent status: it shows counts and a server-calculated release
progress bar. Cancelled rows are excluded from its denominator; Draft rows remain
included. Three Released, five Reserved and two Cancelled rows give **3 / 8 Released
(37.5%)**. An empty or fully cancelled batch shows 0% and “No active crane allocations”.

Crane Project has a read-only crane overview and explicit Complete, Cancel, and
Reopen actions. Reopening requires a correction reason.
Its controller checks that crane rows and draft timesheets are resolved before closure.
ERPNext Project has no Jimmy Cranes hooks or form script.

All booking actions and corrections are recorded in the Assignment or Crane
Project timeline with the user, status change, and reason. Frappe change tracking
remains enabled on the parent documents. Corrections run through the same availability
and work-coverage checks: Undo Release can be blocked if the restored planned
window overlaps another reservation or would leave recorded work uncovered.

## Dates and availability

- Booking dates are inclusive across all Projects and batches. Release on October
  18 makes the crane available from October 19, subject to other bookings and its
  physical condition.
- Reserved rows occupy start through expected end; Released rows occupy start
  through actual release. Early and late releases retain the original planned end.
  Late releases undergo conflict checks and cannot invalidate recorded work.
- An overdue Reserved row remains Reserved and requires explicit release
  confirmation. Availability flags it and blocks new current/future commitments
  until resolved. Historical occupied ranges still use the documented dates.
- Draft and Cancelled rows do not block dates. Maintenance or Inactive physical
  condition blocks new reservations, independently of booking state.
- The crane view and Fleet Reservations Gantt derive reservation, overdue, release
  and recorded-work indicators. No job changes business statuses as dates pass.
- Bulk actions check Project and Assignment permissions, validate selected child
  IDs, lock cranes in a stable order, and save atomically. Concurrent conflicting
  requests cannot both succeed; MariaDB may reject one with a retryable deadlock.

## Timesheets and defaults

Jimmy Cranes Settings remains the single settings DocType. Choosing a timesheet
period fills missing dates with its default day shift times, preserving existing
rows. There is no manual “Fill Missing Dates” button. Assign operators and hourly
rates before saving.

A shift must last more than zero and at most 24 hours. **Ends Next Day** handles
22:00–02:00 and a full 24-hour shift. Midnight ends are exclusive: 20:00–00:00 uses
only the starting day, while 20:00–02:00 requires coverage on both days.

Work must fit a Reserved or Released allocation for the same Project and crane.
Retrospective work is accepted after release while the Project is Open; work after
the actual release is rejected. Closed Projects reject new timesheets. System
Manager or Projects Manager may amend a cancelled timesheet for that same Project
and crane on its original work dates. Submission and cancellation do not change
Project or booking statuses.

Operator hours sum individual intervals. Crane billable hours use their union,
so 08:00–12:00 plus 10:00–14:00 at 100/hour produces 8 operator hours, 6 crane hours
and 600 total. Conflicting hourly rates on overlapping intervals and overlaps with
another submitted crane timesheet are rejected. Submitted documents retain native
Frappe edit protection.

## Sales Items and invoicing

Saving a Crane creates a linked, sellable non-stock ERPNext Item with **Hour** as
its stock UOM. Existing cranes receive an Item when next saved or invoiced.
Each Assigned Crane row has an agreed rental rate and **Hour**, **Day**, or
**Month** rate unit. Each timesheet entry uses its own positive hourly price,
then the assignment's positive **Hour** rate, then the Crane's **Hour** period
price. Hourly invoices use the resulting timesheet amount. Day and Month
invoices use the assignment's rental rate.

**Generate Sales Invoice** on a submitted Crane Timesheet creates a draft invoice
for that sheet. The same action on Crane Project groups its unbilled submitted
timesheets into one draft invoice. The invoice links back to its source sheets;
repeating the timesheet action opens the existing invoice, and project invoicing
skips sheets already linked to an active invoice. Users review and submit the
draft in ERPNext.

When every submitted timesheet already has an invoice link, the Project action
shows the existing Sales Invoices instead of reporting that none can be created.
The **Sales Invoices** view lists each invoice, its source timesheets, status,
total, and warnings for zero totals or missing crane Item lines. A flagged draft
offers **Rebuild Draft Items**: after a reason is entered, it replaces that
draft's items with charges recalculated from its linked submitted timesheets.
Submitted invoices cannot be rebuilt this way. Existing invoices are never
changed merely by opening the Project overview.

Hourly billing uses distinct billable crane hours. Daily billing counts each
crane's worked calendar day once across submitted timesheets in its project.
Monthly billing prorates those distinct worked days by the number of days in
each calendar month. A timesheet must fit one allocation row
with a positive agreed rate. Invoice descriptions show the rate basis; daily
and monthly charges use one service line to preserve currency precision.

## Local development

Crane Project is a separate DocType. No data conversion scripts or database reset
were run. Older local records with retired statuses were left untouched; create
fresh allocations for this workflow.

See [REFACTOR_NOTES.md](REFACTOR_NOTES.md) for the local verification results,
remaining obsolete examples, assumptions, and the exact changed-file list.

With tests enabled on a development site:

```bash
bench --site YOUR_SITE run-tests --module jimmy_cranes.jimmy_cranes.doctype.crane_assignment.test_crane_assignment
bench --site YOUR_SITE run-tests --module jimmy_cranes.jimmy_cranes.doctype.crane_assignment.test_rental_workflow
bench --site YOUR_SITE run-tests --module jimmy_cranes.jimmy_cranes.doctype.crane_assignment.test_rental_concurrency
```

The concurrency test opens independent connections and deletes only its own
explicitly created, committed fixtures. It tests booking and submission races.

## License

MIT
