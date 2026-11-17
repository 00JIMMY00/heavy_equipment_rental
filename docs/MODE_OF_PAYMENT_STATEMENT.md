# Mode of Payment Statement

Open **Crane Operations → Financial Reports → Mode of Payment Statement**.
Select Company, From Date and To Date, and optionally one Mode of Payment.
The default period is the current month through today.

The table shows Date, Mode of Payment, IN, OUT, Balance, Remarks and a source
Document link. Each payment account starts with an Opening Balance from postings
before From Date. Its transactions follow in posting-date order, with a separate
running balance: opening + IN − OUT. The summary cards show opening, period IN,
period OUT and closing balance. The grouped bar chart compares period IN, period
OUT and closing balance for every configured payment account.

Amounts come from active native General Ledger debits/credits in company currency.
This includes receipts, payments, normal/grouped/payroll expenses, direct journals,
POS cash postings and treasury transfers when they affect the configured accounts.
A transfer between two configured accounts appears as OUT on one and IN on the
other. These are fund movements, not rental income/profit or operating expenses.
Draft and cancelled postings are excluded. Expense headers and their generated
journals are counted once. Remarks prefer the expense/transfer description or
individual grouped-expense row description, then the accounting voucher remarks.

Accounts are the current company-specific Default Account rows on Mode of Payment.
Modes without a company account do not appear; selecting one explains the missing
configuration. Disabled modes/accounts remain available for historical statements.
Changing a mode's default account changes the account selected by this report; it
does not reconstruct previous mode-to-account mappings.

Modes using the same account appear together, separated by `/`, and share one
balance and chart category. Filtering by either mode selects that shared account's
complete statement. This avoids duplicating money or inventing a split of an account
balance. Foreign-account movements also use company-currency GL amounts. Balances
use debit minus credit, including any configured custody or liability accounts.

Native GL, Company, Mode of Payment, Account, voucher and contributing app-source
permissions apply. Inaccessible contributing source documents stop the report.
Native print and Excel export are available; running balances are not totaled.
The workspace upgrade adds the link once while retaining other site layout edits.
