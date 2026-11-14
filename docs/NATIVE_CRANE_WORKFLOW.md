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

## Company-owned assets only

Asset recognition is automatic from ownership. Owned → **Company Owned** (full company cost). Shared/other ownership with a positive Company percentage → **Company Interest Only**. Zero Company ownership, Rented and Operated for Owner → no Asset link or Asset creation action. Whole Crane, Pending Review and third-party custody choices were removed.

Only the Company's recognized cost is entered on the native Asset. Example: a crane costs 1,000,000 and our ownership is 40%; our Asset cost is 400,000. Other owners remain in `ownership_partners` for ownership/profit agreements and have no Asset amounts in our books. No owner-value allocation table is displayed. Native purchase/opening/improvement documents must carry the Company's portion; the app cannot infer a total purchase price from percentages or automatically rescale posted Assets.

Migration archives obsolete zero-ownership/custody links and former whole-crane links for partial interests, without changing the underlying Assets or ledgers. A corrected company-interest Asset can then be linked explicitly. Historical ownership changes continue to require native accounting rather than silently resizing posted assets.

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

The user's latest instruction restores the workflow before commit `550f4f5d`: **On Invoice Submission**, **Source Revenue Accounts**, **Invoice Grand Total**, and **no depreciation deduction**. The redesign's alternative selectors are hidden; historical versions and posted ledgers retain their original treatment.

1. Submit the Timesheet; it gets a linked draft settlement.
2. Record all rental costs and complete relevant operating repairs before invoice submission.
3. Submit the Sales Invoice. The same transaction recalculates/submits its settlements and posts external Shareholder entitlements: debit source Income accounts, credit Partners Payable. Deficits or permission failures roll back submission.
4. Record the customer receipt against its invoice. From the settlement, use Partner Payment to review/submit separate native Pay entries, including partial payments.

The calculation is invoice Grand Total → operating percentage → operating costs → remaining-profit percentages. Legacy Net Profit retains its historical allocation account. Historical review/Expense/Equity/depreciation agreements remain calculable under their dated terms; the restoration patch appends new terms rather than changing those snapshots.

Native depreciation still affects the Company's Asset and accounts. It is excluded from the restored contractual distribution pool. Source locks, repair-cost allocation, source Income account/dimension allocation and native payment permissions remain enforced.

Native operating repair costs follow the selected Timesheet, otherwise their service period/Assignment, independently of invoice/stock posting date. Shared costs allocate once by submitted work hours; period calculations prorate deterministically by service days. Rental Profitability uses accounting posting dates and now includes repair stock/service costs and attributed journals/depreciation. Assignment filtering requires explicit attribution; it cannot allocate general depreciation to a job by guessing.

## Migration and practical boundaries

The migration creates no physical Assets, opening balances, stock movements, ownership contributions or corrective entitlement journals. It preserves old Item links, posted invoices, ledgers and dated agreement snapshots. Existing cash maintenance remains Cash Expense. Obsolete full/shared or custody links are archived for correction; posted Assets and ledgers remain intact.

This version deliberately requires perpetual inventory for repair stock accounting. Capitalized external service invoices must be submitted, in company currency, with one Expense account and one Asset Repair allocation; split mixed-purpose bills first. Fully depreciated Asset improvements require the native Asset Capitalization/replacement route supported by the installed ERPNext version. Stock reposts/backdated valuation corrections and component derecognition remain native accounting review tasks. They must not be mistaken for automatic contract allocations.

Review each real contract's recognition and entitlement treatment before changing its effective agreement. ERPNext remains the accounting source of truth throughout.
