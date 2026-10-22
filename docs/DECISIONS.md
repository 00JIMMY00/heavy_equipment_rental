# Current decisions

These reflect the latest user requests and current implementation (2026-10-22):

1. Keep the rental workflow centered on **Crane Assignment** and **Crane Timesheet**. Do not restore the custom `Crane Project` or its old status workflow.
2. A Timesheet has one crane. When no Assignment covers its period, saving creates one using `period_start` and `period_end`; users enter the billing unit and rate once.
3. Drivers are ERPNext Employees. The Timesheet's default driver is optional; individual shift rows may use another driver. Show employee names in the child tables and calculate per-driver hours from shifts.
4. Use a normal Attach field for the Timesheet hard copy, editable after submission. Use Frappe's built-in dashboard for Connections.
5. Billing uses submitted Timesheets and the rate on the Assignment. Preserve overlap checks and avoid double counting crane time when driver shifts overlap.
6. Retain migration patches for legacy records and uploads. Older design documents in the repository can conflict with these decisions; the latest user instruction and current code take precedence.
7. Crane master data includes a license plate. Its active reference prices are Hour, Day, and Month within Crane Details. Historical Year prices are archived in a hidden field during migration. Connections uses Frappe's native dashboard.
8. The Crane image is uploaded from the side panel and must be public; the form has no image section. The linked ERPNext Item shows a read-only copy of Crane period prices. Availability uses a compact monthly reservation calendar and appears only after the Crane is saved.
9. Show the Crane's public image as a thumbnail in the regular List view while keeping its upload field hidden on the form.
10. The linked ERPNext Item uses its native image field to mirror the Crane image, including image changes and removal.
