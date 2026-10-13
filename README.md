# Jimmy Cranes

Crane rental management for Frappe/ERPNext v15. Open **Jimmy Cranes** in Desk for the
rental workspace. **Crane Project is an independent DocType**; new rental records
never use ERPNext Project or Task. ERPNext Customer remains the customer master.

## Records

| DocType | Purpose |
| --- | --- |
| Crane Project | Customer, planned dates, project lifecycle and read-only crane overview |
| Crane Assignment | Non-submittable batch of 100+ crane periods; derived parent status |
| Assigned Crane | Child allocation, planned and actual dates, independent lifecycle |
| Crane | Fleet identity and independent operational condition |
| Crane Period Price | Exactly Day, Month and Year reference prices |
| Crane Operator | Operator master |
| Crane Timesheet | Submittable report for one Project and one header crane |
| Timesheet Entry | One operator's shift and explicit hourly price |

## Workflow

1. Create a **Crane Project** with a Customer and planned dates. Its normal states
   are **Draft → Reserved → In Progress → Complete**, with direct **Draft → In
   Progress** also supported. Use **Actions → Reserve / Start / Complete**.
2. Create one or more Crane Assignments. Add cranes, planned start, expected end,
   and the agreed rental rate snapshot. New rows are Draft and do not block dates.
3. In the assignment's **Actions**, use **Reserve Cranes** or **Start Cranes** and
   select the relevant rows. Starting rows requires an In Progress Project. Project
   actions do not automatically start or reserve every row; booking decisions are
   made with the selected-row actions.
4. Use **Complete Cranes** to release participating cranes, or **Cancel Cranes** for
   cranes that never participated. Cancellation needs a date and reason and is
   refused if any non-cancelled timesheet records work in that allocation.
5. Completing selected rows records their actual end, retains their expected end,
   and recomputes the batch status. Other rows remain in their existing states.
   Project completion is a separate action after every row is Complete/Cancelled.
6. Optional **Automatically Start on Planned Date** on Crane Project defaults off.
   When enabled, the daily scheduler uses the same Start validation as the manual
   action. It starts the Project only. The site's scheduler must be enabled.

The parent assignment status is calculated from all rows: all cancelled →
Cancelled; all terminal with at least one Complete → Complete; any In Progress or
Complete mixed with pending rows → In Progress; otherwise any Reserved → Reserved;
otherwise Draft. It cannot be set independently.

## Dates, availability and maintenance

- Booking dates are inclusive, including across batches in the same Project.
  Completing on October 18 releases October 19 onward. October 18 still conflicts.
- Reserved/In Progress rows use their planned start through expected end. Complete
  rows use actual end; Draft/Cancelled rows do not reserve dates. Extend the plan
  explicitly when continuing beyond the expected end. Late completion requires a
  reason and passes the same overlap checks; the Project dates must also cover it.
- Operational/Maintenance/Inactive is a physical condition. It is never rewritten
  by rental actions. Maintenance/Inactive blocks reservation and activation;
  recording maintenance does not silently cancel an existing contract.
- Crane **Activity and Reservations** displays chosen-date Working/Reserved/Idle,
  availability and future reservations separately.
- **View → Gantt Chart** on Crane Project, or **Fleet Reservations** in the workspace,
  shows planned periods, known actual periods and work markers. Filter by dates,
  crane, Project and row status; scroll or change zoom for large fleets. Click bars
  for assignments, project links for Projects, and work markers for timesheets.
- Unknown migrated actual dates are labelled unknown. No dates are inferred from
  planned periods or hour totals. Their planned period stays blocked conservatively
  until an authorized manager reviews the actual release.

## Timesheets and billing

Select **one crane on the header**; its picker uses the Project and the first work
row's date (or period start). Each row has a date, start/end times, overnight flag,
operator and explicit hourly price. Every touched work day must have an eligible
allocation and be inside the timesheet period; future work is rejected. Completed
allocations remain eligible for historical work through actual release. Complete
Projects allow historical corrections within their verified completion date.

Shifts are longer than zero and at most 24 hours. **Ends Next Day** is explicit.
A shift ending exactly at midnight uses a half-open interval: 20:00–00:00 covers
only the first day; 20:00–02:00 covers both days. Operator hours and informational
line amounts are calculated per row. Crane hours and total amount use the union
of intervals: 08:00–12:00 plus 10:00–14:00 at 100/hour produces 8 operator hours,
6 crane hours and 600 total. Different prices on overlapping time are rejected.
Day/Month/Year prices are reference rates; they never imply an hourly rate.

Submit/Cancel/Amend uses Frappe's standard lifecycle. Submitted records cannot be
edited, and overlapping work cannot be submitted twice for the same crane, even
across Projects. Allocation changes cannot invalidate recorded work. Bulk actions
are atomic and permission checked. Database locks and current reads protect
booking and submission checks under MariaDB repeatable-read isolation; a competing
transaction may receive a retryable Frappe deadlock error instead of a conflict.

System Manager and Projects Manager can submit/cancel/amend. Projects User can
submit/amend but cannot cancel; Project write permission is also checked on rental
writes. Read APIs respect Project, Assignment, Crane and Timesheet permissions.

## Upgrade and preserved history

```bash
bench --site YOUR_SITE backup
bench --site YOUR_SITE migrate
bench build --app jimmy_cranes
```

The versioned patch and idempotent install/migrate hooks:

- Copy only ERPNext Projects referenced by rental documents into Crane Project,
  retaining the same IDs in the separate DocType and preserving the full source
  record in read-only migration history. Existing ERPNext records are retained.
- Move rental Link metadata to Crane Project; remove native Project event hooks,
  JavaScript and dashboard overrides; hide the old rental custom field.
- Copy old `end_date` into `expected_end_date`, map row Working/Completed to In
  Progress/Complete, and derive parent status. Original parent/child records are
  preserved in snapshots; removed metadata columns are not dropped from the DB.
- Preserve old Crane status and map Maintenance/Inactive to physical condition;
  Assigned/Available become Operational. Add missing period price rows without
  replacing existing prices.
- Move a single legacy child crane to the timesheet header. Original approval
  labels and hours remain in a read-only snapshot. Missing shift times require
  review before submission; old Approved records are **not** automatically submitted.
- Stop before model migration if a legacy sheet has multiple/unknown cranes or is
  already submitted and requires an explicit split/history migration policy.

For unknown actual dates use **Actions → Review Legacy Dates** on assignments, then
**Review Completion Date** on migrated completed Projects. Managers must supply
verified dates. Existing conflicting historical records require business review;
upgrading does not cancel, delete or guess corrections for them.

The initial preflight also saves a private source snapshot at
`private/files/jimmy_rental_v2_source.json` when upgrading legacy timesheets.
See [MIGRATION_NOTES.md](MIGRATION_NOTES.md) for the development site's review items.

## Verification

On a development site with `allow_tests` enabled:

```bash
bench --site YOUR_SITE run-tests --module jimmy_cranes.jimmy_cranes.doctype.crane_assignment.test_crane_assignment
bench --site YOUR_SITE run-tests --module jimmy_cranes.jimmy_cranes.doctype.crane_assignment.test_rental_workflow
bench --site YOUR_SITE run-tests --module jimmy_cranes.jimmy_cranes.doctype.crane_assignment.test_rental_concurrency
```

The concurrency test uses two independent connections and removes its explicitly
created committed fixtures. Tests cover project/row lifecycles, bulk atomicity,
100-crane batches, inclusive overlaps, prices, maintenance, overnight coverage,
union billing, immutable submissions, permissions, history, migrations and races.

Manual smoke check: create an unsaved Crane (three prices should already appear),
reserve/start a batch, complete two selected cranes early, try reserving the same
day versus the next day, submit two overlapping operator shifts at one rate, and
open the Project overview and filtered fleet timeline.

## License

MIT
