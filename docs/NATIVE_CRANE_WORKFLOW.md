# Crane-centered native ERPNext workflow

Current design, 2026-11-13. This supersedes earlier assumptions that every crane needs its own rental Item, every repair increases asset value, or every partner distribution reduces sales. Existing posted documents and dated contracts retain their history.

## One operational hub, native accounting

**Crane → Operations** starts bookings, work, repairs, asset/funding documents and owner settlement review. The Crane identifies the physical equipment and holds operational availability, reference rental prices and dated participation agreements. It is not an inventory balance or an accounting ledger.

| Record | Responsibility |
| --- | --- |
| Crane | Physical identity, availability, reviewed Asset link, rental rates, dated owners/operator/profit terms |
| Asset + fixed-asset Item | Acquisition/opening cost, recognized ownership interest, improvements, depreciation, movement and disposal |
| Shared rental-service Item | Product needed by Sales/Purchase Invoice; no physical inventory or depreciation |
| Stock Item + Warehouse | Spare-part quantities and native valuation |
| Crane Assignment / Timesheet | Booking, agreed pricing, Employees and approved actual work |
| Crane Maintenance | Repair job, downtime, cost classification, optional rental-work attribution and links to native postings |
| Stock Entry / Purchase Invoice / Asset Repair / Sales Invoice | Actual repair stock and financial transactions |
| Crane Profit Settlement | Contract calculation, evidence, approval and period/allocation closure |
| Shareholder / Customer / Supplier | Native party roles for participation, amounts billed to an owner, or purchased hire/services respectively |
| Journal Entry / Payment Entry | Funding, recognized entitlements and actual payments |

New cranes reuse Settings → Rental Service Item (`HER-RENTAL-SERVICE` initially). Crane is recorded explicitly on invoice rows, so several cranes can share a product without sharing their costs or revenue. Legacy per-crane Items, invoices, images and prices remain linked; their old mirror behavior remains available. Shared Items do not receive any one crane's name, photo or reference prices.

## Review asset recognition for each contract

The user confirmed that contracts vary. An accounting manager selects **Asset Recognition Basis** before linking an Asset:

- **Whole Crane:** the company recognizes the full Asset under the reviewed ownership/control contract. Other participants' funding is accounted for separately according to its substance.
- **Company Interest Only:** the Asset carries only the company's recognized interest. Do not multiply that already-reduced book value by ownership percentages again. No whole-crane owner valuation table is shown.
- **Third-party Custody:** Rented / Operated for Owner equipment is identified as third-party-owned. Do not capitalize its acquisition or improvements into the company's owned fixed assets.
- **Pending Review:** no asset recognition has been approved. Operational records can still be prepared, but an Asset cannot be linked with this basis.

Selecting a basis posts nothing and never rescales a saved Asset. Changes to actual recognized amounts require native accounting documents. Whole Crane owner reference values are informational; they are neither contribution balances nor liabilities. Ownership percentages and remaining-profit percentages are independently agreed and each total 100%.

An asset participant may use the native Shareholder party record without this workflow issuing company shares. Actual equity issuance, shareholder loans and asset-specific participation are different arrangements. Capital/funding opens an unsubmitted native Journal Entry for accounting to select the correct balance-sheet accounts. Funding and owner drawings are excluded from operating profit; balance-sheet funding journals remain postable after a rental settlement closes. Asset disposal proceeds are also outside rental profit allocation.

## Repairs, including company-owned, shared and external cranes

Start **New Repair** from Crane, select the Company, work dates and Cost Treatment, and save. Use its Create menu to open native drafts, review/submit those documents, then complete maintenance. Linked financial attribution is protected once native documents exist. No second cash expense is generated for native-document repairs.

| Treatment | Native workflow | Accounting result |
| --- | --- | --- |
| Operating Expense | Material Issue for own stock; Purchase Invoice for outside repair services | Debit repair/operating expense, credit stock or supplier payable. Asset cost stays unchanged. |
| Capitalize Improvement | Asset Repair, with justification and a reviewed, submitted company Asset; optional posted service Purchase Invoice | Consumed stock and qualifying services increase the native Asset. Related depreciation schedules remain native. The improvement itself is excluded from operating repair costs. |
| Recover from Owner | Sales Invoice to the owner's Customer, with Update Stock for spare parts | Owner receivable and repair revenue; native stock consumption/COGS. Payment uses native customer receipts. This separate repair activity does not enter rental profit settlement. |
| No Cost | Operational inspection/repair record only | No invented expense or zero-value financial document. |
| Cash Expense | Existing Expense Entry workflow | Retained for direct paid repairs and historical records; not combined with native-document repair costs. |

Ordinary servicing and replacement consumables are expenses. Capitalization requires a qualifying future benefit/major replacement and appropriate derecognition of any replaced component through native asset accounting. It is not a checkbox for increasing profit. See [IAS 16](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2022/issued/part-a/ias-16-property-plant-and-equipment.pdf) and [ERPNext Asset Repair](https://docs.frappe.io/erpnext/asset-repair).

For an external crane, choose Operating Expense when the operating contract charges the rental activity, or Recover from Owner when the owner must be billed separately. Do not deduct a cost from owners' rental profit and invoice them for the same parts. A Supplier-owned crane's owner may also need a Customer record for repair billing; those are separate native party roles. Cross-party netting is an explicit accounting reconciliation, not an automatic deduction.

For Company Interest Only, enter only the improvement amount recognized by the company. Other participants' portions require separate recovery/funding records; the system does not guess legal shares of a repair invoice. Separate jobs/documents handle different cost treatments on the same overhaul.

The app's Asset Repair extension is scoped to HER maintenance. This installed ERPNext version otherwise increases asset value for consumed repair stock even when expense treatment is intended. HER therefore routes routine parts to Material Issue, and uses actual posted stock valuation for capitalization. Cancel the Asset Repair to reverse its stock issue and asset increase together; later repairs must be cancelled first. Its service invoice cannot be cancelled while capitalized. Native stock permissions, insufficient-stock checks, serial/batch handling and accounting permissions still apply.

## Settlement is different from billing and payment

New agreements default to **Review Before Posting**, **Net Revenue** and **Partner Expense**. Accounting must choose the allocation account and contract treatment. Existing agreements retain automatic approval, their historical Grand Total revenue basis, source-revenue posting and prior depreciation policy until explicitly changed with a later effective date.

1. Submit work and invoice the customer normally. The Timesheet gets a draft settlement.
2. Finish posting repair stock, service bills, hire and other expenses. New draft review settlements may show a deficit without blocking the customer invoice.
3. Recalculate; review the source evidence and confirm Costs Reviewed. Open relevant operating repairs must be completed/cancelled. Deficits prevent submitting an entitlement; they never become negative partner payments.
4. Submit the settlement to recognize external entitlements. Payments remain separate native Payment Entries with partial-payment support and owner statements.

The calculation remains: agreed revenue → operating percentage → operating costs → remaining-profit percentages. New Net Revenue agreements exclude invoice taxes; Grand Total remains an explicit compatibility option for old contracts. Recoverable taxes are not distributable revenue under the new default.

Choose partner accounting based on the contract:

- **Partner Expense:** contractual participation owed as a cost of the company's rental activity; debit the reviewed Expense account, credit native partner Payable.
- **Source Revenue Accounts:** agency/net-revenue treatment; reduce the actual attributed revenue accounts. Use only when supported by the arrangement.
- **Equity Distribution:** an approved company-equity distribution; debit a reviewed Equity account, credit partner Payable. An external operator's service fee cannot be treated as an equity distribution by this option.

The operating-first split is a contractual settlement, not a substitute for statutory company profit, cash availability, or dividend approval. No new party payment, capital contribution or dividend is inferred from ownership percentages.

New agreements can deduct **posted depreciation**. Native Depreciation Entry rows referencing the linked Asset are attributed to Crane; only the company/default finance-book scope is included. No depreciation is invented from a rental rate or deducted twice as acquisition/improvement cost. Depreciation allocation currently follows the journal posting date: use a period settlement spanning that date, or Timesheets covering it. It is not automatically spread across earlier workdays. Book ordinary depreciation before approving its associated settlement. Changes to included sources require cancelling/reopening affected settlements; submitted snapshots are immutable.

Native operating repair costs follow the selected Timesheet, otherwise their service period/Assignment, independently of invoice/stock posting date. Shared costs allocate once by submitted work hours; period calculations prorate deterministically by service days. Rental Profitability uses accounting posting dates and now includes repair stock/service costs and attributed journals/depreciation. Assignment filtering requires explicit attribution; it cannot allocate general depreciation to a job by guessing.

## Migration and practical boundaries

The migration creates no physical Assets, opening balances, stock movements, ownership contributions or corrective entitlement journals. It preserves old Item links, posted invoices, ledgers and dated agreement snapshots. Existing cash maintenance remains Cash Expense. Asset links previously approved as whole-cost/custody retain that designation; unlinked equipment needs review.

This version deliberately requires perpetual inventory for repair stock accounting. Capitalized external service invoices must be submitted, in company currency, with one Expense account and one Asset Repair allocation; split mixed-purpose bills first. Fully depreciated Asset improvements require the native Asset Capitalization/replacement route supported by the installed ERPNext version. Stock reposts/backdated valuation corrections and component derecognition remain native accounting review tasks. They must not be mistaken for automatic contract allocations.

Review each real contract's recognition and entitlement treatment before changing its effective agreement. ERPNext remains the accounting source of truth throughout.
