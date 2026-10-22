# Current decisions

These reflect the latest user requests and current implementation (2026-10-22):

1. Keep the rental workflow centered on **Crane Assignment** and **Crane Timesheet**. Do not restore the custom `Crane Project` or its old status workflow.
2. A Timesheet has one crane. When no Assignment covers its period, saving creates one using `period_start` and `period_end`; users enter the billing unit and rate once.
3. Drivers are ERPNext Employees. The Timesheet's default driver is optional; individual shift rows may use another driver. Show employee names in the child tables and calculate per-driver hours from shifts.
4. Use a normal Attach field for the Timesheet hard copy, editable after submission. Use Frappe's built-in dashboard for Connections.
5. Billing uses submitted Timesheets and the rate on the Assignment. Preserve overlap checks and avoid double counting crane time when driver shifts overlap.
6. Retain migration patches for legacy records and uploads. Older design documents in the repository can conflict with these decisions; the latest user instruction and current code take precedence.
