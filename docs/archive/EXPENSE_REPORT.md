# Crane Expense Report — تقرير مصروفات المعدات

Open the highlighted **Crane Expense Report** link under **Crane Operations → Financial Reports**.

Select Company and a posting-date range, then optionally filter by Crane or Crane Timesheet. **More Filters** adds Expense Entry Type, Grouped Expense, Mode of Payment, Cost Center, Employee and Rental Contract. Use **Expense Entry Type** to find a category across documents or **Grouped Expense** to restrict the results to one submitted document. The report starts with the current month.

The **Total Expenses** summary and final table row show the amount for the selected filters in company currency. Unassigned expenses appear as a separate chart and group entry.

**Group By** supports Crane, Timesheet, Expense Type, Mode of Payment and Month. Choose **None** for a flat list. **Show Individual Expenses** displays the rows beneath group totals. Turn it off to show group totals and the final total row. The final total and chart count each matching expense row once.

The chart defaults to spending by Crane. **Chart By** also supports Expense Type and Month. Rankings show the top 11 categories plus Other when more than 12 categories exist, preserving the full chart total. Month charts remain chronological.

The table shows each matching expense row with its posting date, amount, description, payment mode, cost center and employee. Posting date, expense type and payment mode come from the expense row. Cost center and employee come from its Grouped Expense. Open the Timesheet or source expense from the table links. For a flat list or export, choose **Group By → None**.

## Accounting scope

Includes submitted Grouped Expense rows for payroll, cash repairs and manual expenses, including migrated historical records. Historical batch sources are counted only once and shown under their Grouped Expense document. Only posted sources with valid submitted journals in the selected company are included; drafts/cancelled sources are excluded. Missing/invalid journals are reported as errors instead of presenting an incomplete total.

The dates are accounting posting dates. Rental attribution is taken from the saved source links and does not infer a Timesheet from its dates. Supplier purchase invoices, stock consumption, depreciation, partner distributions and unrelated journals are outside this paid-expense report; use Rental Profitability and native accounting reports for those costs.

Account, company and document permissions apply to both source and journal. The report reads existing data and creates no accounting entries.
