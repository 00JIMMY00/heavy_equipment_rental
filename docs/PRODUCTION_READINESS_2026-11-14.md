# Production readiness audit — cranes-dev3

Follow-up: disposed-asset restrictions and company derivation have since been implemented; see PROGRESS.md. The results below describe the original audited commit. Asset master cost is not itself a defect: the opening-ledger observation is a reconciliation check, not a recommendation to change `total_asset_cost`.

**Verdict: hold production release.** The core rental/accounting flows have substantial passing coverage, but a confirmed disposed-asset booking defect, company-default problems, unreliable test fixtures, and unverified deployment/operational controls remain. This audit is not evidence that every possible combination is safe.

Audited site: `cranes-dev3.arab-erp.com`. Application commit: `a8a69e48f99f80d6043195dbba8a260ea608e07e`. Frappe and ERPNext: `15.122.0`. Audit started 2026-11-14. No application behavior, schema, posted business data, or dependency source was intentionally changed. This deliverable adds audit documentation only.

- [All 145 executed test cases and module totals](PRODUCTION_AUDIT_CASES_2026-11-14.md)
- [Machine-readable results, original tracebacks, probes and integrity checks](PRODUCTION_AUDIT_RESULTS_2026-11-14.json)

## Results and method

**Original unmodified suite: 139 passed, 5 failed, 1 skipped.** All five failures subsequently passed in diagnostic reruns after controlling their fixtures; this does not turn the original run into a green suite. The production code was unchanged in those reruns. Two failures expose real default-company workflow weaknesses as well as fixture assumptions.

The app contains 145 discoverable cases in 13 effective suites; the standalone maintenance test file contains no test methods. Cases ran serially against dev3's actual Frappe/ERPNext controllers, SQL database, GL and payment ledger. A temporary `cranes company` (EGP) and employee supplied fixtures expected by the tests. Each case used a database savepoint and rollback. The runner called individual unittest cases rather than Frappe's committing class setup; there are no custom class setup methods in these app tests. This is a controlled integration run, not a claim that the normal `bench run-tests` invocation is reproducible on a fresh site.

Additional checks:

| Check | Result / boundary |
|---|---|
| Native asset purchase → Asset → supplier payment | Passed: 100,000 acquisition, balanced fixed-asset/payable GL, outstanding reduced to zero |
| Native Asset scrap → new Crane Assignment | **Failed business expectation: booking accepted** |
| Native Asset restore | Passed; restored the probe asset's Partially Depreciated status |
| Shared crane in company A, site default company B | Wrong-company Assignment and 2,000 draft SI created; submission correctly blocked by company guard |
| Currency allocation | 1,000 deterministic randomized cases; signed amount conservation at 2 decimal places, 1–100 nonnegative weights |
| Existing GL | No unbalanced active vouchers; this is an arithmetic check, not proof of correct recognition or attribution |
| Source/journal integrity | No broken submitted Expense Entry or positive-entitlement CPS journal links |
| Python/JSON | 130 Python files parsed; app JSON parsed without syntax errors |
| Calendar frontend build | Passed (2,160 modules); bundle-size warning around 561 kB remains |
| Browser | Eight existing document forms loaded without JavaScript page errors; calendar and distribution dashboard loaded; mobile Crane page had no horizontal overflow at 390 px |

Browser coverage was a page-load smoke check, not a full interactive role-based UAT of every button, grid, export or mobile form. Accounting transactions were exercised through the actual controllers by the integration tests and probes.

A database/public-files/private-files backup was created before testing under:
`sites/cranes-dev3.arab-erp.com/private/backups/20261114_212925-cranes-dev3_arab-erp_com-*`.
The backup was not restored during this audit. Probe/test transactions were rolled back; the temporary company is absent. The temporary browser authentication session was deleted. Existing cancelled records and amendments were preserved, not deleted or rewritten.

## Findings requiring action

### F1 — High: disposed assets remain rentable

**Reproduction:** create and submit a native Asset, link it to a Crane, scrap it through ERPNext's native `scrap_asset`, then insert a new Assignment for that crane. Asset status was `Scrapped`; the booking succeeded.

`crane_assets.py:26` checks disposed status when establishing/changing the Asset link. `crane_assignment.py:78` only rejects new/changed bookings for an operationally `Inactive` crane. Native Asset scrapping does not make the linked Crane inactive. Preserving the historical link is reasonable; allowing new work without an availability check is the defect.

**Small fix:** centralize a current operational eligibility check, invoked for new/extended bookings and new work submission. Reject linked Assets that are cancelled, Sold, Scrapped or Capitalized, with a clear message. Preserve historical work and allow its corrections/cancellations. Define restoration behavior explicitly; do not erase history or automatically cancel valid accounting documents.

**Release tests:** owned and shared cranes; scrap/sale/cancel/capitalization; existing booking before disposal; disposal followed by Timesheet submission; restoration; historical correction; unlinked and zero-company-ownership cranes. Only the scrap/new-booking case was transactionally reproduced here; the other statuses require their own regression cases.

### F2 — Medium, high for multi-company use: company defaults create unusable rental drafts

**Reproduction:** crane and Asset belong to `cranes company`, site default is `test`. Save a Timesheet without an existing Assignment. The generated Assignment and 2,000 Sales Invoice use `test`. Invoice submission is rejected with “belongs to another agreement Company.” No wrong-company posted invoice was demonstrated.

`crane_timesheet.py:124` creates the Assignment without a company. `billing.py:181` uses Assignment company or default company. Cash Expense maintenance can similarly receive a default company inconsistent with its selected work; its context validation then rejects it.

**Small fix:** derive the new Assignment/maintenance company from the selected work and crane agreement/Asset where unambiguous, and validate agreement/Asset/company consistency before creating downstream drafts. Require an explicit company if ambiguous. Recheck when company/crane/work changes; reject incompatible multi-crane Assignments early. Keep the existing submission guard.

**Release tests:** two companies with deliberately conflicting user defaults; owned/shared/rented cranes; Assignment-first and Timesheet-first; cash/native repairs; company changes after recorded work; company-restricted users. Setting an explicit correct company made both affected integration cases pass.

### F3 — Medium: test fixtures are not independent of site configuration

Five original failures and their diagnostic results:

| Original failing case | Evidence / diagnosis | Diagnostic rerun |
|---|---|---|
| `test_multiple_source_income_accounts_returns_and_dimensions` | Expected 17,000 revenue, got 55,000. Copied invoice retained pricing fields; its requested 1,000 rate became 20,000, producing 60,000 extra invoice and −20,000 return. Settlement matched the posted documents. | Passed after explicitly resetting copied price-list/discount/margin/pricing-rule fields; original assertions retained. |
| `test_unrelated_journal_keeps_native_party_validation` | Selected Expense account has blank account type. ERPNext's `validate_account_party_type` rejects only a nonempty disallowed type, so no exception was raised. HER did preserve the ordinary journal's party. | Passed with explicitly typed `Expense Account`; no HER production change. |
| `test_review_settlement_includes_repair_and_posts_selected_expense` | Tax account belongs to fixture company but generated SI belongs to site default `test`. Patching only `erpnext.get_default_company` was insufficient because Assignment was already defaulted. | Passed after explicitly setting generated Assignment company before submission. |
| `test_maintenance_rental_context_carries_to_expense` | Cash maintenance inherits a company inconsistent with selected Assignment. | Passed with explicit maintenance company. |
| `test_draft_invoice_account_stays_local_to_demo` | Test assumes an Item Default row already exists for its company. Row lookup was absent; assertion queried a nonexistent row. | Passed with explicit company-specific child fixture. Intermediate normal Item saves also inherited an invalid default warehouse; final diagnostic inserted a controlled child fixture directly. |

Keep the original failures visible. Fix fixtures to create their own company, accounts, employees, Item Defaults, pricing inputs and payment modes. Do not weaken financial assertions to obtain a green run. Replace the direct child-fixture diagnostic with a valid normal fixture builder for permanent tests. Run the normal test runner on an isolated test site after these changes.

The skipped `test_removed_manual_terms_are_archived_without_repricing` requires retired database columns absent on this fresh site. Test it on a restored pre-migration database; skipping is not migration validation.

### F4 — Go-live accounting data: reconcile the existing Asset opening

The saved Asset `ACC-ASS-2026-00001` is an existing Asset with gross value 400,000, no purchase invoice/receipt and depreciation disabled. Current active Asset-root GL balances total 5,460, so this value is not supported by an acquisition/opening posting in the current development ledger. The master link intentionally does not create such postings. This is a go-live data reconciliation task, not evidence that linking should post an acquisition automatically.

Before importing opening balances, reconcile the chosen Company-interest recognition value to the Asset register, fixed-asset/accumulated-depreciation GL, capital/funding entries and the approved depreciation schedule. Do not simply copy this development opening into production.

Saved amended cycle at the final check: SI 10,000 fully paid; expense costs 1,600; CPS external entitlement 4,440 and company retained 3,960; partner payment 4,440. Original expense/CPS and their original partner payments remain cancelled. The Timesheet links to the active amended CPS. These are observed balances, not transactions created by this audit.

## Business coverage established by passing cases

- Booking/date/rate validation, overlapping work, multiple drivers, distinct crane hours, Hour/Day/Month billing, existing Assignment terms, duplicate invoicing prevention, rented-crane supplier quantities and purchasing.
- Shared ownership with independent ownership/profit percentages, operating-first and historical calculation modes, multiple revenue accounts, signed returns, grand-total allocation, taxes in settlement basis, zero balances, deficit rejection, period gaps/overlaps, dated agreements and immutable snapshots.
- Work/service-period expenses versus posting dates; direct Timesheet costs, Assignment costs and shared cost allocation; no repeated allocation; late costs and closed-source protection.
- Automatic settlements on invoice submission, review-mode settlement with repairs, native Shareholder entitlements, partial/full/combined payments, outstanding selection and payment allocation.
- Native Cancel scopes for expense, SI, Timesheet and CPS; customer receipts; partner payments; combined payments; shared expenses; changed scope; permission denial and atomic rollback; native Amend with fresh journal and updated links.
- Native Asset link uniqueness, company/quantity checks, company-owned-interest valuation without applying ownership twice, dated ownership, link correction audit, and permission checks.
- Routine parts/service repairs, stock valuation, serialized consumption, capitalization and reversal, depreciation schedule regeneration, recovery from owner, and preventing duplicate cash expense recognition.
- Profitability/distribution/partner/treasury reports; draft versus posted totals; historical/as-of payments; no double counting across shared invoices; permission-denied sources; treasury funding excluded from profit; import repeatability and rollback.

The exact method names and original outcomes are in the 145-case inventory. A passing suite demonstrates its stated assertions, not every variation of the broader category.

## Code redundancy review

These are targeted cleanup candidates, not reasons to rewrite the app before launch:

1. `rental_validation.py:42` (`action_date`) and `:123` (`billable_totals`) have no references found in app code. Confirm external integrations before removing them.
2. `Crane.after_insert` and `Crane.on_update` both call `ensure_sales_item` and `sync_crane_item_prices`; inserts run both hooks. Consolidate the redundant insert work if native lifecycle ordering tests remain green.
3. `rental_expenses.guard_expense` and `affected_settlements` duplicate work-window/Assignment/Timesheet matching. Share a selector while preserving the latter's additional snapshot lookup.
4. The maintenance standalone test class is empty. Integration tests cover repairs, but focused status transition and maintenance-condition tests should be explicit.
5. Context docs retain superseded asset policies below current overrides. Consolidate the current policy and retain old decisions as dated history to reduce implementation mistakes.

Keep historical migration patches, old agreement readers and supplier compatibility until an actual data migration removes their need. They preserve accounting history; they are not dead code merely because new documents use Shareholders. Keep whitelisted functions referenced from JavaScript even when Python references are absent.

Billing locks Assignment/Timesheets before later crane locks, while Timesheet validation locks Crane before Assignment. This warrants a consistent lock-order review and concurrency tests; no deadlock was reproduced in this serial audit.

## Remaining release test matrix

These checks were **not fully demonstrated** in this audit. Execute applicable cases against a production-like restored copy before sign-off.

| Area | Required scenarios / acceptance criterion |
|---|---|
| Disposal/availability | F1 variants above; no new work on disposed assets, historical records retained |
| Multi-company | F2 variants above; company chosen correctly at source, no downstream cleanup needed |
| Actual roles | Dispatcher, accountant, accounts manager, read-only and company-restricted users; UI and API create/read/write/submit/cancel/amend; fail atomically without hidden financial data exposure |
| Concurrency | Simultaneous overlapping bookings, double invoice generation/submission, duplicate CPS posting, payment versus cancellation, expense versus settlement, stale preview after dependency changes; one valid result or clear retry, no duplicate postings |
| Asset lifecycle | Sale with gain/loss and cancellation, disposal after depreciation, Asset Movement, value adjustment, CWIP-to-use, purchase receipt then invoice, acquisition returns, multiple finance books, depreciation catch-up and cancellation |
| Accounting close | Frozen periods, fiscal year boundaries, backdated corrections, cost-center restrictions, reconciliation/unreconciliation, native repost jobs and rounding/write-off cases |
| Contract variations | Actual production VAT/withholding/discount/round-off policy; foreign currencies if allowed; zero-value/free hire policy; hourly work above clock duration; owner operating fees and cost burden approved against sample contracts |
| Maintenance | Multiple simultaneous jobs, Planned/In Progress/Completed/Cancelled transitions, blocked reopening, cancelled expense replacement, asset disposed during repair; correct operational condition after each action |
| Migration | Restore a real older schema; run patches twice; verify archived fields, immutable historical journals/snapshots, attachments and totals; include the skipped retired-column test |
| Browser UAT | Complete new shared-crane cycle with ordinary roles, cancellation warning and resubmission, partial payments, printing/exports, Arabic/mobile entry, multi-tab stale forms |
| Scale | Realistic years of Timesheets/GL/settlements, report and cancellation-preview timings, expensive scans, worker queue duration; no load target was supplied or benchmarked |
| Operations | Production process configuration, scheduler/worker supervision, backup restore rehearsal, off-host retention, monitoring, HTTPS/session configuration, deployment rollback and asset-cache invalidation |

Current dev3 has `developer_mode=1`, a running development `bench serve`, an enabled scheduler and one worker observed. That verifies a functioning development setup, not production deployment readiness. A backup exists; disaster recovery remains untested.

## Recommended release sequence

1. Fix disposed-asset eligibility and company derivation with focused regression cases. Avoid new buttons or a new accounting subsystem.
2. Make the five tests self-contained and cover the skipped migration on an upgraded fixture. Require an unmodified green suite.
3. Run actual-role and concurrent posting/cancellation tests, then the applicable native Asset/accounting-close matrix.
4. Reconcile opening Assets/GL, verify production infrastructure and restore a backup.
5. Rehearse one approved shared-crane cycle with company Asset, costs, invoice, customer receipt, partner entitlement/payment, Cancel warning, Amend and resubmission. Reconcile reports to native GL/payment ledger and retain the signed expected figures.

No production deployment or functional fixes were performed by this audit.
