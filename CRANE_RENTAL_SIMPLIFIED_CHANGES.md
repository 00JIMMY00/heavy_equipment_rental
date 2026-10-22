# Crane Rental App — Simplified Architecture Changes

## Goal
Make the app **simple to use, but powerful enough for real crane-rental operations**. Remove `Project` from the crane-rental workflow. Users must be able to start with either a booking or a Timesheet.

## Core DocTypes

| DocType | Purpose |
|---|---|
| **Crane** | Physical crane; central dashboard for rentals, work, maintenance, costs and billing. |
| **Crane Assignment** | Customer rental/booking agreement. Can contain **multiple cranes** in an `Assigned Crane` child table, each with its own dates and agreed pricing. |
| **Crane Timesheet** | Actual work for **one crane and one location**, with multiple dated `Timesheet Entry` rows (operators, hours and overtime). |
| **Crane Maintenance** | Operational maintenance record; **not submittable**. |

## Relationships
- **Remove all `Project` links and dependencies** from custom crane-rental workflows; do **not** delete ERPNext's native Project DocType.
- Each `Crane Timesheet` **must link to exactly one `Crane Assignment`** and one `Crane`.
- One `Crane Assignment` can have **many Timesheets**; one Timesheet belongs to **one Assignment**.
- Keep `Assigned Crane` and `Timesheet Entry` as child tables.
- Put the `crane` field on the **Timesheet parent**, not on every entry. Use `Employee` for company-employed operators.

## Two Simple Entry Points

**A. Assignment first**
1. Create an Assignment with customer, location, cranes, full rental periods and agreed rates (Hour / Day / Month).
2. Create Timesheets against the applicable crane in that Assignment.

**B. Timesheet first — automatic Assignment (approved)**
1. User starts a Timesheet and selects **Crane, Customer, Location** and work dates.
2. If the correct Assignment already exists, link to it; if there are multiple plausible matches, ask the user to choose.
3. Otherwise, ask for the **full agreed rental period** (e.g. Oct 1–30), billing unit and rate. **Do not infer the rental period from Timesheet dates.**
4. Create a **single-crane Assignment** automatically and link the Timesheet to it, in one server-side transaction.
5. Further Timesheets for that same rental **reuse the Assignment**; never create a new Assignment for each Timesheet.

## Minimal Business Rules
- Validate that the Timesheet's crane belongs to its linked Assignment and that customer/location agree.
- Validate work dates against the agreed rental period; extend the Assignment deliberately if the rental continues.
- Prevent conflicting bookings for the same crane. Derive availability from Assignment date ranges; **no manual `Released` status**.
- Make **Crane Timesheet submittable**; use submitted work as the operational basis for invoicing.
- Generate **Sales Invoices directly**, using agreed Hour / Day / Month rental terms and approved Timesheets, without requiring a Sales Order. Prevent double billing and double-counting multiple operators' hours.
- Keep accounting entries in standard ERPNext documents; show linked invoices and expenses from the Crane dashboard rather than duplicating them.

## Design Principle
**One rental agreement, many Timesheets, zero Projects, minimal clicks.** Reuse native ERPNext features and avoid unnecessary DocTypes, statuses and manual steps.
