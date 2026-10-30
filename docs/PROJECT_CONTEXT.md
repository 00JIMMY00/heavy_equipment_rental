# Project context

Heavy Equipment Rental is a Frappe/ERPNext app for booking cranes, recording work, and billing rentals. The current user goal is a simple workflow with two entry points: create a **Crane Assignment** first, or create a **Crane Timesheet** that creates/reuses an Assignment.

- Assignment holds customer, location, cranes, rental dates, billing unit, and agreed rate. Its date ranges prevent overlapping crane bookings.
- Timesheet is for one crane. Its period dates also become the rental dates when it creates an Assignment. Operator Shifts record work by ERPNext Employee; an optional default driver fills new rows, and each row can be changed.
- Rented Cranes link an ERPNext Supplier. Their Timesheets record purchase unit, quantity, and price for the Timesheet period; submitting creates and submits a Purchase Invoice for the linked Crane Item. Create → Payment on the Crane or submitted Timesheet opens a native draft supplier Payment Entry against an unpaid invoice.
- Timesheet shows hours by driver, a hard-copy attachment that remains available after submission, and Frappe's native Connections dashboard. Submitted work feeds draft Sales Invoices.
- The custom `Crane Project` DocType was removed. ERPNext's native `Project` is separate from the rental workflow. Legacy project data was migrated to Assignment/Timesheet links before removal.
- The app also includes crane maintenance, expenses, and a rental calendar/timeline. It requires `arab_erp_theme` for the shared Expense Entry and Expense Entry Type DocTypes; the rental app adds optional Crane and Crane Assignment links to Expense Entry and integrates maintenance expenses. HER owns its industrial theme, logo, favicon, and loading assets, layered over the base theme without modifying its source or changing workspace structure.

Start with [README.md](../README.md). Core code is in `heavy_equipment_rental/heavy_equipment_rental/doctype/`, billing in `heavy_equipment_rental/billing.py`, and migrations in `heavy_equipment_rental/patches/` plus `heavy_equipment_rental/patches.txt`.
