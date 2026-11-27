# Recent verification

| Date | Development-site milestone |
| --- | --- |
| 2026-11-27 | Migrated cranes-dev3 for HER holiday dates and Timesheet row colors. Verified both color pickers, holiday and zero-hour styling in Chrome, and all six rental workflow tests. |
| 2026-11-27 | Added operating repair stock issues to Crane Expense Report under the crane selected on Maintenance. Reconciled two existing issues on cranes-dev3 and checked the document links in Chrome. All 22 maintenance posting and expense report tests passed in isolated runs using the site's default company. |
| 2026-11-27 | Migrated cranes-dev3 for transfers between payment modes. Chrome verified the two selectors, read-only accounts for the selected company and collapsed optional details. All 45 treasury, payment statement, workbook, expense, demo and rental workflow tests passed. |
| 2026-11-27 | Audited static and dynamic deletion links for 509 records across 20 DocTypes on cranes-dev3. Reproduced repair voucher cycles, verified native deletion in four rolled-back cases, and confirmed that a submitted Maintenance amendment still protects its source. All 257 distinct HER tests passed across isolated runs. |
| 2026-11-27 | Verified deletion of draft settlement CPS-00010 followed by cancelled Timesheet TS-00011-1 on cranes-dev3 in a rolled-back transaction. The cancelled payroll vouchers and journal entries were preserved. |
| 2026-11-27 | Updated Crane Timesheet on cranes-dev3 to accept shifts over 24 hours and recognize overnight shifts automatically. All 41 Timesheet and rental workflow tests passed. |
| 2026-11-22 | Updated both dispatch reports with source drill-downs, charts, human-readable crane links and scoped totals. Verified a filtered repair cost of 1,400 against its source amounts, chart, card and total on cranes-dev3. |
| 2026-11-22 | Migrated cranes-dev3 for fleet utilization and maintenance downtime. Verified both reports and the Crane Insights table in Chrome. Dispatch can record an in-progress repair using Maintenance Status. All 26 fleet report, rental workflow and maintenance posting tests passed. |
| 2026-11-22 | All 22 profitability, distribution and rental workflow tests passed on cranes-dev3. Browser checks covered voucher drill-downs, five distribution views, advanced filters and narrow screens. |
| 2026-11-21–22 | Delivered separate salary earnings and withdrawals, advances, overtime payroll and amendment fixes. Added treasury balances and revised receivable, partner and salary reporting. |
| 2026-11-19 | Verified the audit fixes on cranes-dev3. All 233 distinct HER cases and 13 deployment and manifest tests passed across the recorded runs. |

Earlier test results, deployment evidence, reset receipts and treasury reconciliation exports are in the [historical archive](archive/).
