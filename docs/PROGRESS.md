# Progress

As of 2026-10-22:

- Simplified Assignment/Timesheet entry, removed the custom `Crane Project` DocType, and migrated historical links while leaving native ERPNext `Project` intact.
- Removed duplicate rental date entry on Timesheets; a new Assignment uses the Timesheet period. Added optional default driver, per-row driver overrides, hard-copy attachment, native Connections dashboard, and a calculated Hours by Driver table.
- Backfill patches preserve earlier signed uploads and populate driver names/hour summaries on existing Timesheets. The local development site `cranes-dev2.arab-erp.com` was migrated and the rental workflow test passed after these changes.
- Updated the Crane form with image, license plate, simplified pricing, today's availability, and native Connections. Added a patch to preserve previous Year prices in a hidden legacy field.
- Migrated `cranes-dev2.arab-erp.com` and passed the rental workflow test after the Crane changes.

For the next change: inspect `git status` first. Use the commands in [README.md](../README.md) for migration and tests, and update this page with meaningful new milestones.
