# Simplified crane workflow — local refactor

Specification: `CODEX_SIMPLIFY_CRANE_WORKFLOW.md`.

## Repository findings and resulting design

The starting implementation used a separate Crane Project DocType, a derived
Crane Assignment status, five child booking states, Project Reserve/Start actions,
status cascades, a daily start job, and legacy conversion patches. It already had
inclusive date conflicts, crane locks, bulk selection, a one-crane timesheet model,
overnight calculations, billing unions, release progress, and a Gantt view.

The refactor reuses native ERPNext Project. Assignments are status-free containers;
only child allocations store Draft, Reserved, Released or Cancelled. Native Project
hooks enforce explicit closure after allocations and draft timesheets are resolved.
Rental Projects use Manual percent completion; unrelated native Projects retain
Task completion behavior. No core files or new DocTypes were introduced.

The custom Project source, legacy-state handlers/conversion patches, and scheduled
start code were removed. Timesheet arithmetic and native submission protection are
preserved. Read APIs and dialogs use crane names. The Project overview remains
read-only, and the Gantt distinguishes booking periods from recorded work.

## Decisions and assumptions

- All draft Crane Timesheets require a decision before Project closure: submit or
  remove them. Both Completed and Cancelled use this rule.
- After Project closure, only System Manager / Projects Manager amendments of a
  cancelled Timesheet for the same Project and crane are accepted. Corrections
  may use only dates present in the cancelled source.
- Overdue Reserved allocations require explicit release confirmation before a
  new current/future commitment can be made. Historical dates use the documented
  inclusive allocation windows.
- Bulk Release uses one chosen release date for the selected rows; select separate
  groups when their release dates differ.
- Native expected Project dates are displayed read-only on assignments. They are
  planning information; crane start/end and effective release dates govern booking
  and work eligibility.
- No data migration or database reset is required or performed. Retired tables and
  unused old columns remain in the local database; they are not part of the new
  app model. No legacy-status interpretation was added.

## Verification

Site: `cranes-dev2.arab-erp.com`.

- 30 workflow tests passed (including the final native-Project and metadata checks).
- 1 schema test passed.
- 1 real concurrency test passed, covering competing reservations and submissions
  on independent database connections: exactly one writer succeeds in each race.
- Python Ruff checks, compilation, JavaScript syntax and JSON validation passed.
- No browser interaction test was run.
- Existing DocType/workspace metadata was reloaded directly; no data conversion
  patches were run. The obsolete Scheduled Job Type was removed.
- `allow_tests` was restored to false. No existing rental records were deleted,
  converted, or reset. Concurrency fixtures were explicitly cleaned up.

Pre-existing record counts remained: 6 native Projects, 9 retired Crane Projects,
8 Crane Assignments, 13 Assigned Crane rows, and 7 Crane Timesheets.

## Existing local examples requiring recreation

These records were left untouched. Their old states or links are incompatible
with the new workflow; they are not automatically mapped.

- Removed child states: ASG-00003 row 1, ASG-00004 row 1, ASG-00013 row 1,
  ASG-00014 row 1, ASG-00015 rows 1–2, ASG-00016 row 1 (five Complete, two In Progress).
- Assignments whose Project IDs exist only as retired custom Projects:
  ASG-00012 → CP-00007, ASG-00013 → CP-00008, ASG-00014 → CP-00009,
  ASG-00015 → CP-00010, ASG-00016 → CP-00011.
- Timesheets whose Project IDs are custom-only: TS-00010 → CP-00008,
  TS-00011 → CP-00009, TS-00012 and TS-00013 → CP-00010.
- TS-00001, TS-00002 and TS-00003 lack shift intervals required by the current
  timesheet model. Views spanning those old records can reject invalid data.

To exercise the refactor, create a fresh native Project from the workspace, add a
fresh Assignment, Reserve its Draft rows, and enter actual Timesheets. Release or
Cancel those rows and explicitly close the Project. Old examples can be reviewed
and removed separately if desired; no destructive cleanup is needed for tests.

## Exact changed files

- `M` `README.md`
- `A` `REFACTOR_NOTES.md`
- `M` `jimmy_cranes/hooks.py`
- `M` `jimmy_cranes/jimmy_cranes/doctype/assigned_crane/assigned_crane.json`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane/crane.js`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane/crane.json`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane/crane.py`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_assignment/crane_assignment.js`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_assignment/crane_assignment.json`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_assignment/crane_assignment.py`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_assignment/test_crane_assignment.py`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_assignment/test_rental_concurrency.py`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_assignment/test_rental_workflow.py`
- `D` `jimmy_cranes/jimmy_cranes/doctype/crane_project/__init__.py`
- `D` `jimmy_cranes/jimmy_cranes/doctype/crane_project/crane_project.js`
- `D` `jimmy_cranes/jimmy_cranes/doctype/crane_project/crane_project.json`
- `D` `jimmy_cranes/jimmy_cranes/doctype/crane_project/crane_project.py`
- `D` `jimmy_cranes/jimmy_cranes/doctype/crane_project/crane_project_dashboard.py`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_timesheet/crane_timesheet.js`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_timesheet/crane_timesheet.json`
- `M` `jimmy_cranes/jimmy_cranes/doctype/crane_timesheet/crane_timesheet.py`
- `M` `jimmy_cranes/jimmy_cranes/page/crane_project_gantt/crane_project_gantt.js`
- `M` `jimmy_cranes/jimmy_cranes/workspace/jimmy_cranes/jimmy_cranes.json`
- `D` `jimmy_cranes/migration.py`
- `M` `jimmy_cranes/patches.txt`
- `D` `jimmy_cranes/patches/v2_independent_projects.py`
- `D` `jimmy_cranes/patches/v3_assignment_progress.py`
- `A` `jimmy_cranes/project_events.py`
- `A` `jimmy_cranes/public/js/project.js`
- `M` `jimmy_cranes/rental_operations.py`
- `M` `jimmy_cranes/rental_queries.py`
- `M` `jimmy_cranes/rental_validation.py`
