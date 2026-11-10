# Automatic Timesheet settlements — current workflow (2026-11-10)

Configure the sharing Crane once. Select Company, native **Shareholder** partners, ownership/residual percentages and operator. The Company **Partners** Payable account and cost center default automatically; choose a different enabled company-currency Payable account if necessary. Shareholders receive their default party account too. This does not issue company shares or alter share capital.

1. Submit the Timesheet: one draft settlement is created with Timesheet, Crane and work dates.
2. Generate its Sales Invoice: the settlement displays the linked invoice.
3. Submit the Sales Invoice: its settlement is automatically approved and the native entitlement Journal Entry is posted in the same transaction. A deficit, invalid agreement, missing permission or failed journal rejects invoice submission. This automatic posting was explicitly selected by the user.
4. Open the settlement → **Create → Partner Payment**. If multiple partners remain unpaid, choose one. A native **Pay** Payment Entry opens with that partner's outstanding balance and journal allocation. Submit it through ERPNext; partial payments are supported. The settlement shows live posted/pending amounts, paid/adjusted balances, status, and links to its draft/submitted payments.

A shared invoice is apportioned across its submitted Timesheets by their billable value, preserving exact currency totals. Crane costs posted in overlapping work periods are allocated by submitted billable hours; direct linked hire costs use their invoice links. Candidates and weights are retained with source evidence. After closing work, reverse the relevant settlements before changing captured sources, returns or overlapping Timesheets. Corrections can use normal cancellation/amendment. The older period-based workflow remains available, but cannot distribute a source already used by Timesheet settlements.

Open **Crane Operations → Crane Partner Statement** for detailed entitlement/payment movements and totals, or **Crane Partner Summary** for totals by Shareholder and aging. Both expose invoice value, posted/pending entitlement, paid/adjusted amount, outstanding amount and status, using native Payment Ledger entries up to Report Date. Optional filters select partner, crane, Timesheet, posting period and status. The totalable invoice value is allocated across external partners so shared invoices are counted once; full settlement invoice value is also displayed.

Migration creates account/identity defaults and links historical Timesheets to their existing settlements when evidence is unambiguous. Historical supplier journals, payments, agreements and amounts remain unchanged. A historical period settlement keeps Period basis even if its single Timesheet is displayed. Existing historical records are not automatically posted again.

The earlier calculation/period notes below describe the retained accounting rules; their manual creation/approval and Supplier identity instructions are superseded above.

---

# Crane operating and distribution agreements

Current workflow, 9 November 2026. One agreement covers a sole owner, several
owners/partners, and a company/external operator. Ownership does not determine
profit entitlement automatically.

## Configure once

Choose Shared Ownership, Operated for Owner, or Operated by Partner on Crane.
Owned/Other may enable sharing; Rented retains the separate supplier hire flow.
Enter Agreement Company, Effective From, Operator and **Operating Share of Grand
Total %**. The agreement company is fixed after the first version.

In the partner table enter Supplier, Ownership % and **Remaining Balance %**.
Each percentage column must independently total 100%. Include Our Company only
when it owns a share or receives some of the remaining balance. An operator with
no ownership/residual share does not need a company row: its operating entitlement
appears automatically in settlement results. External operators must be selected
from the partner Suppliers. Operated for Owner means our company operates with
zero ownership (it may still have an agreed residual share). If our company is
also assigned positive ownership, the form and server classify the agreement as
**Shared Ownership** automatically, preserving its operating rate and all ownership/
remaining-balance percentages. Normal effective-date and history controls still
apply; this does not change earlier agreement versions or settlements.

For a sole owner with 10% operating entitlement to our company: operating rate
10%, one Supplier row with ownership 100% and remaining balance 100%. For several
partners, enter each partner's separately agreed percentages. The operator may
also receive a percentage of the remaining balance.

For a company that both owns and operates the crane, use **Shared Ownership**,
Operator **Our Company**, the operating rate, and an Our Company row with its
ownership and remaining-balance percentages. The company receives both its
operating entitlement and its residual share.

Accounts Manager/System Manager sets the collapsed Accounting Setup section:
company-currency Supplier Payable account and Cost Center. Operating First uses
the source revenue accounts automatically. The allocation Expense/Equity account
is shown and required only for historical Legacy Net Profit agreements. Normal source/journal/payment permissions still apply.

## Calculation and sources

New agreements use Operating First:

```
Operating entitlement = round(Revenue × Operating %, currency precision)
Balance after operating = Revenue − Operating entitlement
Remaining balance = Balance after operating − Operating costs
Partner residual = Remaining balance × Agreed remaining balance %
Partner total entitlement = Operating entitlement (if operator) + Partner residual
```

The current business scenario has **no taxes**: invoice net amount and Grand Total
are equal. Revenue uses submitted Sales Invoice **base_grand_total** in company
currency. The settlement never adds taxes itself. It is not rounded total, cash
collected or invoice outstanding.
Allocate each invoice Grand Total proportionally across all its signed base net
item amounts, then select this crane's items. This includes a proportional share
of invoice taxes/charges and preserves discounts already in item net values.
Allocation conserves the invoice total using deterministic largest-remainder
currency rounding. It does not assign the whole invoice to each crane. Signed
returns reverse the allocation. Zero-net/zero-grand invoices retain their signed
item values; zero-net invoices with non-zero Grand Total stop for review.

Rental invoice items carry Crane automatically; historical invoices use their
Timesheet/Item links. Ambiguous links fail rather than invent an allocation.
Ordinary Sales/Purchase Invoice Items may also carry Crane. Purchase costs use
**base_net_amount**, as before. Expense Entries require an explicit Crane and a
valid submitted, same-company Journal Entry. Explicitly Crane-tagged journal
Income/Expense rows contribute signed amounts; native balance-sheet rows do not.
Do not record the same expense in several unrelated source documents.

Sources use posting dates and company currency. Submitted unbilled work is not
revenue. Draft/cancelled sources, treasury funding, payments, and settlement
journals are excluded. Each linked source requires read permission. Historical
unposted expenses stop settlement; this workflow never repairs them automatically.

**Deficit rule:** if operating costs exceed the balance after operating, saving
and submission both fail with revenue, operating entitlement, remaining balance,
costs and shortfall. Submission recalculates, so a previously saved draft cannot
bypass newly posted expenses. No settlement payable is posted and no new loss is
carried forward. Negative revenue also stops for review. Exactly zero remaining
balance is valid; the operating entitlement is still due.

Example: Grand Total 100,000; operating 10% = 10,000; costs 20,000; remaining
balance 70,000. At 50/30/20, partners receive 35,000 / 21,000 / 14,000. If costs
are 91,000, the 90,000 after operating is insufficient by 1,000: stop.

**Reviewed no-tax example:** revenue 100,000, operating costs 20,000 and external
owner entitlements 70,000 leave 10,000 for our company. With the expense-allocation
account used by the demo, the posted accounting result is also 10,000. Raising the
operating percentage to 12% leaves 12,000. See [the actual posted examples and
journal explanation](OPERATING_FIRST_DEMO.md).

## Settle, pay and change terms

A **Crane Profit Settlement** is the period calculation and approval document.
It retains the agreed terms, sources, operating entitlement and partner shares.
Its submission creates a separate native Journal Entry recognizing external
entitlements; payment is a later native Payment Entry. It is not itself a cash
payment.

Create → Profit Settlement suggests the next consecutive period, ending no later
than today or the next agreement change. Save/Recalculate refreshes sources and
results; Submit recalculates, snapshots terms/sources/shares and closes the period.
Results show operating, residual and combined amounts for each party, plus total
company retention and external payables. Rounding conserves the full remainder.

Operating First external entitlements post a native Journal Entry reducing the
Income accounts of the source invoice items and attributed income journal rows,
then crediting Supplier Payable for each partner's combined total. Allocate the
external total proportionally to signed source revenue, preserving cost center,
project, custom accounting dimensions and currency rounding. Returns reduce their
original account's weight; negative account allocations post credits. Source
snapshots retain the accounts/dimensions, and Posted Revenue & Costs shows the
revenue account links. Legacy Net Profit retains its configured allocation account.
Previously submitted settlements and journals are never rewritten by migration;
correct a specific unpaid settlement by native cancellation and amendment,
preserving its original records. No cash/bank posting occurs until Partner Payment. A company's retained share needs no extra posting. No zero-value journal
is created. Create → Partner Payment opens a draft native Payment Entry; ERPNext
handles partial/full payment and remaining balances.

Use **Change Agreement**, enter a later effective date, edit operating/ownership/
remaining-balance terms, then save. The date must follow the previous version and
all submitted settlements. Split periods at agreement changes. Historical
snapshots stay fixed. Explicit inactive intervals can be skipped; crane locking
serializes agreement/source/settlement postings and prevents duplicate closure.

Closed-period source submission/cancellation is blocked. Post corrections in an
open period, or cancel settlements latest first after cancelling/unreconciling
allocated payments. Direct cancellation of the settlement journal is blocked.

## Preserve existing data

The operating-first migration marks pre-existing agreement versions as Legacy
Net Profit without rewriting their JSON history. Original submitted amounts,
source snapshots, payments and links remain intact. Additional display fields
show the previous total as residual with zero operating entitlement.

Legacy dated versions still calculate on net sales for their original dates.
New/changed versions must use Operating First. All newly calculated settlements,
including legacy periods, reject deficits. Existing historical carried losses
remain recorded and must be recovered before switching to Operating First;
migration never erases or distributes a historical balance.

## Verification

```bash
bench --site cranes-dev2.arab-erp.com migrate
bench --site cranes-dev2.arab-erp.com run-tests --module heavy_equipment_rental.heavy_equipment_rental.doctype.crane_profit_settlement.test_crane_profit_settlement
bench --site cranes-dev2.arab-erp.com run-tests --app heavy_equipment_rental --skip-test-records
```

The development site supplies the fixture company and accounting defaults. The
last command skips unrelated generated ERPNext fixtures (the site's optional
Payment Gateway DocType is not installed). Tests use real controllers/ledgers
and roll back their own records. Use the explicit demo command in the numerical
demo to retain reviewable sample documents on the development site.
