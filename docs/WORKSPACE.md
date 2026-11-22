# Crane Operations workspace

Open **Crane Operations** (`/app/crane-operations`). The latest layout has a shallow crane panorama and seven section cards in four desktop columns. The cards contain compact icon/link rows, colored headings and permission-filtered record counts. Mobile layouts stack the native blocks.

The workspace navigation starts closed on a fresh page load. The menu button beside the page title opens it; your toggle choice is preserved during subsequent workspace updates. The title area and sidebar share a straight edge and a continuous navy background. On desktop the full-height sidebar scrolls independently. On mobile you can close the panel with the menu button, Escape, a navigation link, or a tap outside the panel.

## Edit on your site

1. Sign in as Administrator or a user with **Workspace Manager**.
2. Open Crane Operations and click the native **Edit** button at the bottom (shown as **تصحيح** in the installed Arabic translation).
3. Hover over a card and use its **pencil** button to change its **Label** or **Card Links**. Add a row, choose **Link Type** (DocType, Page or Report), choose **Link To**, and set its label. Confirm the dialog.
4. Use the drag handle to reorder blocks and the resize handle to change widths. Click heading/text blocks to edit their text. Use the block **+** control to add a Shortcut, Card, Heading or other native block. A shortcut's pencil edits its destination and label.
5. Click **Save** at the top right. **Discard** leaves the saved arrangement unchanged.

Edits affect this shared workspace and survive app migrations. Record counts refresh automatically and respect record permissions; they are totals, not open/outstanding counts. Colors, row icons and pill styling come from the app stylesheet; the native editor changes content and layout, not the theme CSS.

A System Manager can assign Workspace Manager to the people responsible for the shared layout. This role controls workspace editing; it does not grant access to the accounting or rental documents behind the cards. Normal document/report permissions still apply. No developer mode is required. Users who want a separate layout can use Frappe's workspace duplication feature to create a private copy.

## Installation and persistence

`sync_operations_workspace()` installs the new layout once per site, tracked by the internal default `her_operations_workspace_layout_v2`. Later calls leave the workspace untouched, including intentional deletions. The template lives outside the standard module Workspace directory, and the live workspace has no Module, so migration imports and developer-mode exports cannot replace the site's arrangement.

The first upgrade preserves the previous full Workspace JSON in `private/backups/her-workspace-before-v2.json`. Keep it for administrative recovery. The upgrade retains existing access roles and other widget definitions. It does not delete old Pages or Custom HTML Blocks. Future changes to the bundled template apply to new sites only; existing sites should use Edit.

For an existing site, apply this presentation-only update with:

```bash
bench --site YOUR_SITE execute heavy_equipment_rental.workspace.sync_operations_workspace
bench --site YOUR_SITE clear-cache
```

Then reload the browser. Standard installation/migration also runs the initializer. No rental DocType schema or accounting changes are involved.

The regenerated panorama displays at 10:1 with a maximum height of one quarter of the viewport. The Sections/الأقسام heading has been removed.

The Mode of Payment Statement is under Financial Reports. Its one-time upgrade patch adds only the report link and preserves the site's other links and layout.

**Simple Receivable Summary** is also under Financial Reports. Installation and migration add its link once to the saved workspace.

## Crane Insights

Open **Crane Insights** at `/app/crane-insights` for the stakeholder dashboard. Fleet size and condition reflect the current visible Crane records. The 7-, 30- and 90-day controls apply to submitted Crane Timesheets ending in the selected period, through today. Each timesheet contributes its full billable hours on its end date. Working cranes have positive hours in the period. The ranking links the five highest-hour cranes to their records.

The workspace uses the existing System Manager, Projects Manager, Projects User and Accounts Manager roles. Figures respect record permissions. Viewers without Timesheet read access see the fleet snapshot and an access message for work metrics. Installation and migration create the workspace and update its app-managed dashboard block. To install just the dashboard, run `bench --site YOUR_SITE execute heavy_equipment_rental.crane_insights.install_workspace` and clear the site's cache.

The compact yellow and navy dashboard lists every visible crane, including those with zero expenses. Expand a crane to inspect dated charges and open their Grouped Expense documents. Expense cards count submitted crane-linked batches and lines by **row posting date** in the selected period. Totals are shown separately per currency. Expenses without a crane are excluded. Grouped Expense read access is required for amounts and details.

## Fleet utilization and maintenance reports

Open **Crane Operations → Operational Reports**. Both reports accept a date range and an optional crane. **Crane Insights** shows the selected period’s crane-day figures and links to the full availability report.

**Fleet Utilization and Availability** counts distinct calendar days per crane. The utilization percentage divides worked booked days by booked days through yesterday within the selection. Simultaneous drivers count once. An overnight shift counts each day it occupies and a shift ending at midnight counts only the preceding day. Submitted zero-hour days show downtime. A past booked day without a submitted entry shows as missing. A worked day takes precedence over a zero-hour entry on the same crane and day. Maintenance is counted separately and can overlap work. The fleet percentage weights each elapsed booked crane-day equally.

**Next Free From / Free Through** gives the first opening from today or the selected start date, whichever is later. A blank start means the crane is unavailable or its booking schedule is only partly visible. A blank end on an available crane means the schedule has no later booking.

**Maintenance and Downtime** shows in-progress and completed repairs overlapping the selected dates. Set the existing **Status** field to **In Progress** and save when work starts. Submit the job when repairs finish. An open repair continues through today even when its form has a default end date. **Repair History** shows the full inclusive duration, next active or upcoming booking, and cost. Filter by crane to see that crane’s cost totals in each currency. **Bookings at Risk** lists each open repair alongside its bookings overlapping the 30 calendar days beginning today. A booking linked to multiple open repairs counts once in the summary.

Repair costs use completed cash amounts, visible posted expense-account movements for stock, supplier services and owner-recovery costs, or the final submitted Asset Repair amount for improvements. A dash means there is no visible recorded amount. A no-cost repair shows zero. Repair totals include each selected job once, regardless of how many bookings it affects.

Click a crane name to open its record. Click day counts or utilization to inspect dated bookings, timesheets and maintenance. The utilization chart divides elapsed booked days into worked, recorded downtime and missing entries. Repair costs open their contributing documents. The table closes with a separate total per currency.
