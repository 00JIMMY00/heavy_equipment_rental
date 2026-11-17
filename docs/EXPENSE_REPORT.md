# Crane Expense Report — تقرير مصروفات المعدات

Open the highlighted **Crane Expense Report** link under **Crane Operations → Financial Reports**.

Select Company and a posting-date range, then optionally filter by Crane or Crane Timesheet. **More Filters** adds Expense Entry Type, Mode of Payment, Expense Source, Rental Contract and Driver. The report starts with the current month.

The summary cards show total expenses in company currency, individual expense-line count, distinct assigned cranes and the average per calendar day in the selected range. Unassigned expenses are included in the total and appear as a separate chart/group; they are not counted as a Crane.

**Group By** supports Crane, Timesheet, Expense Type, Mode of Payment and Month. Choose **None** for a flat list. **Show Individual Expenses** displays the rows beneath group totals; turn it off for totals only. Group totals already contain their detail rows, so do not sum both levels. The summary cards and chart always use individual expense rows once.

The chart defaults to spending by Crane. **Chart By** also supports Expense Type and Month. Rankings show the top 11 categories plus Other when more than 12 categories exist, preserving the full chart total. Month charts remain chronological.

Open the source expense, Timesheet, Rental Contract or Journal Entry from the table links. Native report print and export remain available; select Group By → None for an export containing only individual expense rows.

## Accounting scope

Includes submitted normal Expense Entries (including payroll and cash-expense repairs), direct-journal Grouped Expense rows, and historical Grouped Expenses that generated Expense Entries. Historical batch sources are counted only once and shown under their Grouped Expense document. Only posted sources with valid submitted journals in the selected company are included; drafts/cancelled sources are excluded. Missing/invalid journals are reported as errors instead of presenting an incomplete total.

The dates are accounting posting dates. Rental attribution is taken from the saved source links and does not infer a Timesheet from its dates. Supplier purchase invoices, stock consumption, depreciation, partner distributions and unrelated journals are outside this paid-expense report; use Rental Profitability and native accounting reports for those costs.

Account, company and document permissions apply to both source and journal. The report reads existing data and creates no accounting entries.
