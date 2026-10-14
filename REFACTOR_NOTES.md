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

Verification: 28 workflow tests, 1 schema test, and 1 concurrency test passed.
`allow_tests` was restored to false.
