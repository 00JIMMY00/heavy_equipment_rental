# HER industrial theme

HER's visual layer lives entirely in `heavy_equipment_rental`; the shared expense theme app is unchanged.

- `public/css/industrial_tokens.css`: palette, native Frappe aliases, light/dark modes, reduced-motion loader source. Root selectors intentionally outrank base-theme tokens when that app loads later.
- `public/css/industrial_desk.css`: navigation, existing workspace sidebar/cards, forms, lists/grids/reports, buttons, dropdowns, and dialogs. No workspace definitions or DOM reordering.
- `public/css/industrial_loading.css`: native splash and `#freeze` presentation. `.grid-form` backdrops are explicitly excluded. Frappe still controls insertion, request nesting, and dismissal.
- `public/css/industrial_web.css`: login styling scoped to `#page-login`.
- `public/js/industrial_login.js`: anonymous login follows the system color preference; it does not change Desk's saved theme or authentication behavior.
- `public/branding/`: a 512px main logo (`mobile-crane-logo.png`) and multi-size favicon derived from the supplied **Yellow Mobile Crane Truck with Raised Boom.png**, the unmodified **AR_Crane_Loader_Reverse_Loop.gif**, and a still frame for reduced-motion users. The earlier `logo.png` remains available for existing links; the distinct main-logo filename avoids reusing a cached previous logo. Assets are local; no CDN or new font dependency.
- `frontend/src/industrial.css`: matching calendar and timeline surfaces. Main initializes presentation from the user's existing Desk theme preference, supplied in the calendar boot context. It does not write user preferences.
- `branding.py`: idempotent presentation settings only. It can run separately from `setup.execute`, avoiding workspace/permission synchronization for theme-only deployments. Recognized defaults from Frappe, ERPNext, Arab ERP, or previous HER branding are replaced; unrelated custom branding remains unchanged.

Keep semantic status colors, document editor dimensions, responsive breakpoints, focus visibility, and print rendering intact. Use token-based styling for additional components. The GIF is cached normally and is only rendered in active native loading states; no minimum display time or extra request blocking is added.

Build and apply with the commands in the README. The Vite build retains `/assets/heavy_equipment_rental/branding/` URLs for Frappe to serve at runtime. Its large-chunk advisory belongs to the existing calendar bundle; this theme adds no JavaScript dependency.

For browser verification, check Desk/workspace, a list, a form with child rows, link suggestions, a report, a dialog, and login in light/dark modes; check 320px and 390px widths and RTL. Confirm nested `frappe.dom.freeze()` calls require matching `unfreeze()` calls, grid editor backdrops have no crane overlay, and reduced-motion mode loads `loader-still.png`. Compare workspace, DocType, Custom Field, and permission snapshots before/after a theme-only deployment.
