# Current decisions

## Booking and billing

- Contract dates reserve the crane. Reject overlapping bookings. A Timesheet can span consecutive bookings on the same contract when each working shift fits one booking. Future shifts are allowed.
- New sales and supplier terms use Hour or Day. Bill from submitted shift terms so later edits to contract or master prices preserve approved work. Preserve legacy Month terms and exact dates covered by flat-rate invoice lines. Cancelling a daily charge reopens its dates even if an overtime invoice remains.
- Concurrent drivers each earn their own hours. Count overlapping crane time once and reject overlapping shifts for the same employee. A zero-work, zero-overtime row records downtime and can omit driver and clock times.

## Accounting and corrections

- Driver earnings accrue on Timesheet submission. A submitted salary expense records the withdrawal. Advances may exceed earnings, giving a negative salary balance. Payroll uses driver hours and rates independently of customer billing units and prices.
- Each new Grouped Expense row posts its own dated Journal Entry. Charge a linked Timesheet directly, or allocate a crane-and-contract cost across eligible submitted Timesheets by billable hours. A crane-only expense stays outside settlement allocation. Count each posted cost once, including older Expense Entry-backed batches.
- Apply saved crane shares when calculating drafts. Preserve submitted settlement snapshots. Current settlements take Invoice Grand Total, deduct operating fees, then eligible costs, and distribute the remainder. Exclude depreciation and block a shortfall. Recognize external entitlements against source revenue and the Shareholder payable.
- Recognize only the company's ownership interest in a native Asset. Supplier hire takes precedence over legacy owner rows. Changes in ownership percentages do not revalue posted Assets.
- Run directed cancellations atomically with native permissions and accounting locks. Timesheet cancellation reverses dependent postings. Cancelling a settlement reverses its entitlement while preserving upstream work and billing. Amendments retain the original document history and resolve fresh accounting links.

## Compatibility and reporting

- Preserve the in-place Rental Contract and Grouped Expense renames, existing IDs, legacy assignment fieldnames and historical posting paths. Reuse native ERPNext Project independently of rentals. Migrations must preserve submitted vouchers and ledgers.
- Measure booked utilization through yesterday using submitted work. Distinguish missing records from recorded downtime. Count overlapping maintenance once per crane-day and treat In Progress as open until completion. Dispatch covers active bookings and bookings starting within 30 days.
- Use posted account movements for treasury reporting. Count each account once when several payment modes share it. Keep Treasury Workbook searchable for custody reconciliation and workbook-format exports.
