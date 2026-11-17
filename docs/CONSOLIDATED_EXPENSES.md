# مصروف مجمع — Consolidated Expense

Open the highlighted **Consolidated Expense / مصروف مجمع** link in the Accounting card of Crane Operations. It replaces the workspace's Expense Entries entry point; historical Expense Entries remain accessible through search, rental Connections and the generated row links.

Choose Company, Crane, one Crane Timesheet and an optional Driver. The Timesheet supplies the Rental Contract and its CPS link. Choose a default Mode of Payment and optionally a Cost Center. All rows charge this same rental work; dates are their actual accounting posting dates and may differ from the rental dates, following existing expense attribution rules.

Add Date, Description and Total in the table. Open the pencil editor to change Expense Entry Type or Mode of Payment for an individual row. New rows inherit the company's expense type from **HER Settings → Consolidated Expenses → Expense Defaults by Company**, and the form's payment method. Existing row overrides are preserved.

**Download Excel Template** provides a bilingual `.xlsx` workbook. Fill its Expenses sheet without changing the headings. Date, Description and Total are required. Dates accept Excel dates or YYYY-MM-DD. Type and payment method are optional: blank cells use form defaults. A type may be its stored ID or a unique enabled title for the company, such as `عام`. Payment methods use their exact stored names. Formulas, invalid totals, ambiguous types and files over 2 MB / 1,000 data rows are rejected. **Upload Excel Template** appends validated rows to the draft; a confirmation shows new and identical rows; identical rows are skipped and existing rows are never overwritten. Review the rows and total before saving/submitting.

Save creates no accounting. Submit creates one submitted Expense Entry and balanced native Journal Entry per row, with that row's date, description, amount, account and payment method. Crane, Timesheet, Rental Contract, Driver and Cost Center flow into those sources. Existing profitability, treasury and CPS logic reads the generated Expense Entries, so the batch is not a second expense source. Expense Entry links are available in the pencil editor and Connections.

Cancel the batch to reverse all generated expenses/journals together. Direct cancellation of an individual generated expense is blocked. Existing submitted CPS closures must be reopened first; normal accounting period and permission controls still apply. Any posting/reversal failure rolls back the whole request. Amend makes fresh generated documents and retains the cancelled history.

Installation/migration supplies a company-specific `عام` Expense account and enabled Expense Entry Type, then fills only missing HER default selections. This is a portable, idempotent fixture implemented in setup rather than exporting site-specific Company/Account IDs. New companies receive the same defaults once their chart exists. Existing selected types and all historical transactions are preserved. No payment account is guessed: configure the default payment method and its company account explicitly.

Verified on `cranes-dev3.arab-erp.com`; production deployment is separate.
