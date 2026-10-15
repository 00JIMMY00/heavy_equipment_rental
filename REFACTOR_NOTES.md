# Crane Project workflow refactor

Specification: `CODEX_SIMPLIFY_CRANE_WORKFLOW.md`, with the user's later
requirement to use a separate Crane Project instead of ERPNext Project.

Crane Project is the app's project record. Crane Assignment and Crane Timesheet
link to it. ERPNext Project has no Jimmy Cranes hooks or form script. Crane
Project is Open until explicitly Completed or Cancelled; closure checks for
unresolved allocations and draft timesheets. Assignment remains status-free;
Assigned Crane rows use Draft, Reserved, Released, and Cancelled.

Crane Project was already present in the local database. Its source files were
restored with the simplified workflow. Metadata for Crane Project, Assignment,
and Timesheet was reloaded on `cranes-dev2.arab-erp.com`. No data conversion or
database reset was performed. Historical rows with retired statuses remain and
may require separate manual review.

Verification: 36 workflow, correction, and billing tests, 1 schema test, and 1 concurrency test passed.
`allow_tests` was restored to false.

## Sales invoicing addition

Crane now creates a linked non-stock sales Item in the same database transaction
when saved. Submitted Crane Timesheets can generate a draft Sales Invoice from
the agreed rate on their single covering Assigned Crane row. A Crane Project
action groups its unbilled submitted Timesheets. Invoice links on source sheets
prevent repeat billing while the invoice exists and is not cancelled.

On the local site, ERPNext's standard Address/Contact custom fields were absent.
Its own setup routine restored those metadata fields so Sales Invoice validation
could run. No rental records were converted or reset. The billing tests cover
hourly, daily, and monthly calculations, same-day deduplication across
timesheets, and cancellation protection.

## Reversible booking corrections

Crane Assignment now offers Undo Reserve, Undo Release, and Undo Cancel actions.
Each correction requires a reason, writes an assignment timeline entry, and
passes the regular conflict and recorded-work checks in one transaction. New
cancellations retain the prior status so Undo Cancel can restore it. Legacy
cancelled rows require the user to choose Draft or Reserved. Crane Project can
be reopened with a reason, and its status change is recorded in its timeline.

The local ASG-00033 row was inspected without changing it: its Crane Project is
Open, no conflicting reservation was found, and its recorded work fits inside
the planned window. Undo Release should be available through the new action.

## Existing draft invoice discovery

CP-00027 has two submitted timesheets linked to draft Sales Invoices
ACC-SINV-2026-00002 and ACC-SINV-2026-00003. Both drafts were edited after
generation to zero-value test Items; their source links still exist. The Project
action now returns linked invoices when no submitted sheet needs a new invoice,
and its overview flags missing crane Items and zero totals. An explicit,
reasoned Rebuild Draft Items action recalculates items from linked submitted
timesheets. Read-only calculation for the two existing drafts yields 300 EGP
and 480 EGP respectively. Neither existing draft was changed during this work.
