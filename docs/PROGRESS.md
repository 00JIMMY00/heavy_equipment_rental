# Progress

As of 2026-10-22:

- Simplified Assignment/Timesheet entry, removed the custom `Crane Project` DocType, and migrated historical links while leaving native ERPNext `Project` intact.
- Removed duplicate rental date entry on Timesheets; a new Assignment uses the Timesheet period. Added optional default driver, per-row driver overrides, hard-copy attachment, native Connections dashboard, and a calculated Hours by Driver table.
- Backfill patches preserve earlier signed uploads and populate driver names/hour summaries on existing Timesheets. The local development site `cranes-dev2.arab-erp.com` was migrated and the rental workflow test passed after these changes.
- Updated the Crane form with image, license plate, simplified pricing, today's availability, and native Connections. Added a patch to preserve previous Year prices in a hidden legacy field.
- Migrated `cranes-dev2.arab-erp.com` and passed the rental workflow test after the Crane changes.
- Moved Crane image controls to the side panel, defaulted uploads to public, added a public-image migration, synced reference prices to a read-only Item table, and replaced Availability with a compact monthly reservation view hidden on new Cranes.
- Migrated `cranes-dev2.arab-erp.com` and passed the rental workflow test for the Item price sync and public image requirement.
- Added a photo thumbnail column to the regular Crane List view without changing side-panel image upload.
- Synced the Crane image to the linked Item's native image field and added a backfill patch for existing Items.
- Fixed Crane DocType field arrangement validation by moving the list thumbnail flag from `Attach Image` to a mirrored hidden Data field; existing thumbnail URLs are backfilled.

For the next change: inspect `git status` first. Use the commands in [README.md](../README.md) for migration and tests, and update this page with meaningful new milestones.
