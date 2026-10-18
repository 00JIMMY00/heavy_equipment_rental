# Development migration — 13 October 2026

Site: `cranes-dev2.arab-erp.com`.

## Completed

- Database backup created before edits:
  `private/backups/20261013_122302-cranes-dev2_arab-erp_com-database.sql.gz`.
- Four referenced projects copied into independent **Crane Project** records:
  `PROJ-0002`, `PROJ-0003`, `PROJ-0004`, `PROJ-0005`.
- Three Crane Assignments, four allocation rows and three Crane Timesheets retained.
  Their Project links now resolve to Crane Project. The six original native Project
  records were compared with the preflight snapshot and are unchanged.
- Both Crane masters retain their original status in migration history; operational
  condition is now independent. Six Day/Month/Year price rows added.
- Raw source records retained in document snapshots and the site's private
  `private/files/jimmy_rental_v2_source.json`. Unknown actual dates were not filled.

## Records requiring business review

| Record | Preserved issue | Next step |
| --- | --- | --- |
| ASG-00003 / CR-00001 | Originally Completed for October 13–16, with no actual dates | Verify whether it participated and its actual dates; use Review Legacy Dates for a completed contract |
| ASG-00004 / CR-00001 | Originally Completed for October 1–11, with no actual dates | Verify actual participation and release |
| ASG-00004 and ASG-00005 / CR-00001 | Existing overlapping October reservations across projects | Reconcile the source records and timesheets; the upgrade has not invented a cancellation or release to remove this conflict |
| PROJ-0003 and PROJ-0004 | Originally completed without an actual completion date | Review assignment dates, then use Review Completion Date |
| TS-00001 | Original hours retained; its Project PROJ-0002 currently has no allocation | Verify the original allocation/Project before entering shift intervals |
| TS-00001, TS-00002, TS-00003 | Old records store hour totals, without shift boundaries or hourly rates | Enter verified start/end times and agreed hourly prices before submission |
| TS-00002 | Original label Approved but original `docstatus` was 0 | Approval label is preserved; it was not silently converted into a submitted record. A manager must review it |

Historical inconsistencies may block edits until corrected. These are preserved
source-data issues, not newly created reservations. Do not guess actual dates,
delete source history, or bypass booking checks to clear them.

## Verification

- All 24 automated workflow, migration, and real concurrent-write tests passed on this site.
- Browser checks: Crane Project overview, unsaved Crane default prices, fleet
  timeline controls and unknown-date labels, and bulk row-selection dialog.
- Python lint, JavaScript syntax checks, and app asset build passed.
- Temporary browser session removed and `allow_tests` restored to false.

Use **Heavy Equipment Rental → Crane Project** for rental projects, or Desk route
`/app/crane-project`. The fleet timeline is `/app/crane-project-gantt`.
