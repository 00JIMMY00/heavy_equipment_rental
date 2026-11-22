# Project context

HER is a Frappe/ERPNext v15 app for booking cranes, recording work and posting the resulting business transactions. It depends on ERPNext and arab_erp_theme. The Desk entry point is **Crane Operations**.

## Rental workflow

1. Save a **Rental Contract** to reserve one or more cranes for a customer, location and date range. From a **Crane Timesheet**, users can also select a matching contract or create one for the work period.
2. Submit a Timesheet for one crane on one contract. It records dated shifts, drivers, work, downtime and overtime. When supplier hire is enabled on the Timesheet, submission also posts the supplier Purchase Invoice.
3. Generate a draft **Sales Invoice** for submitted, unbilled work. For a sharing crane, the Timesheet creates a draft **Crane Profit Settlement**. Complete costs before submitting the Sales Invoice. Under the current sharing policy, invoice submission posts partner entitlements. Collections and partner payouts use native Payment Entries.
4. Use **Grouped Expense** for expenses and salary payments. Use **Crane Maintenance** for repairs, stock parts, supplier services and improvements. The maintenance treatment determines which accounting documents it creates.

## Where to look

- Rental entry, billing defaults, existing records and test commands are in the [README](../README.md). The [user guide](USER_GUIDE.md) has worked examples.
- For cost attribution, payroll payments and partner accounting, see [Grouped Expense](CONSOLIDATED_EXPENSES.md), [driver payroll](../README.md#driver-payroll) and [profit sharing](PROFIT_SHARING.md).
- **Fleet Utilization and Availability** and **Maintenance and Downtime** are under Operational Reports. Crane Insights shows work, downtime, missing days and next availability per crane. See [workspace reporting](WORKSPACE.md#fleet-utilization-and-maintenance-reports).
- For release, backup and rollback procedures, see the [deployment runbook](../deploy/README.md).
