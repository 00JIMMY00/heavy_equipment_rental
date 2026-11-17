# Crane Operations workspace

Open **Crane Operations** (`/app/crane-operations`). The latest layout has a shallow crane panorama and seven section cards in four desktop columns. The cards contain compact icon/link rows, colored headings and permission-filtered record counts. Mobile layouts stack the native blocks.

The menu button beside the page title opens the workspace navigation. The title area and sidebar share a straight edge and a continuous navy background. On desktop the full-height sidebar scrolls independently. On mobile you can close the panel with the menu button, Escape, a navigation link, or a tap outside the panel.

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
