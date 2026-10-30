# Progress

As of 2026-10-27:

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
- Added Create actions on saved Cranes for Expense, Maintenance, Timesheet, and Sales Invoice. The invoice action groups submitted, unbilled work by Assignment.
- The rental workflow test passed with two new draft invoices across two Assignments and no duplicate invoices on retry.
- Removed rental-owned logo and theme assets/hooks and declared `arab_erp_theme` as a required app. Migrated historical Expense Types and Expense Entry amounts to the shared models, linked maintenance to shared types, and handed prior site branding to the base theme. Migrated `cranes-dev2.arab-erp.com`; both rental workflow tests, including completed maintenance expense posting, passed.
- Added an optional Crane Assignment link to the shared Expense Entry alongside the existing optional Crane link. A saved Crane Assignment now offers Create → Expense with its Assignment prefilled.
- Enabled title display for the shared Expense Entry Type links so Expense Entry expense rows show the type name instead of its ID.
- Added HER-owned industrial light/dark styling for Desk, login, calendar, and timeline, using machinery yellow, graphite, and steel gray. Integrated the supplied crane PNG as logo/favicon and GIF into native splash/blocking loaders plus the calendar refresh indicator, with a static reduced-motion fallback. All changes live in this app; no changes to `arab_erp_theme` or Frappe/ERPNext source.
- Built HER assets with `bench build --app heavy_equipment_rental` and the calendar frontend with `npm run build`; applied presentation-only branding on `cranes-dev2.arab-erp.com` without migration or rental setup. Browser checks passed for both themes, login system-theme changes, 320px/390px layouts, RTL form presentation, lists, a native report table, link suggestions, dialogs, nested loaders, startup splash dismissal, reduced motion, and child-row editor backdrops. Fixed narrow timeline toolbar overflow. Snapshot comparisons confirmed all 23 workspaces and their child records, DocTypes, Custom Fields, and Custom DocPerm records remained unchanged. Python/JavaScript syntax and whitespace checks passed. No rental workflow or schema changes were made.

- Set the supplied yellow mobile crane PNG as the main Desk/login/app logo under a distinct `mobile-crane-logo.png` URL so browsers request the correct image instead of reusing the earlier logo URL.

- Refined native form tabs to share a continuous bar background in both themes, removing the alternating white blocks. Active tabs use a consistent yellow underline; hover and keyboard focus keep the shared surface intact.

For the next change: inspect `git status` first. Use the commands in [README.md](../README.md) for migration and tests, and update this page with meaningful new milestones.
