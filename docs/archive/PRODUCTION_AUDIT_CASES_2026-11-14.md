# Executed production audit cases — 2026-11-14

Original suite: **139 passed, 5 failed, 1 skipped**. See [findings and diagnostic reruns](PRODUCTION_READINESS_2026-11-14.md). These results are the original unmodified tests, not adjusted pass totals.

| Suite | Pass | Fail | Skip |
|---|---:|---:|---:|
| TestCrane | 13 | 0 | 0 |
| TestRentalWorkflow | 3 | 0 | 0 |
| TestCraneProfitSettlement | 28 | 1 | 0 |
| TestCraneTimesheet | 13 | 0 | 1 |
| TestTreasuryTransaction | 9 | 0 | 0 |
| TestCraneRentalProfitability | 5 | 0 | 0 |
| TestCraneConnections | 6 | 0 | 0 |
| TestDistributionReporting | 10 | 0 | 0 |
| TestExpenseParties | 6 | 1 | 0 |
| TestNativeCraneWorkflow | 12 | 1 | 0 |
| TestPartnerSettlements | 27 | 1 | 0 |
| TestRentalItemDefaults | 1 | 1 | 0 |
| TestTreasuryWorkbook | 6 | 0 | 0 |

## TestCrane

| Test method / business scenario | Original result |
|---|---|
| `test_asset_draft_and_basis_follow_company_ownership` | PASS |
| `test_company_mismatch_rejected_from_crane_and_native_asset` | PASS |
| `test_company_share_is_not_applied_twice_and_future_terms_do_not_reprice_asset` | PASS |
| `test_default_finance_book_is_used_instead_of_first_book` | PASS |
| `test_duplicate_asset_and_grouped_assets_rejected` | PASS |
| `test_legacy_unlinked_cranes_remain_saveable` | PASS |
| `test_link_changes_and_financial_reads_require_permissions` | PASS |
| `test_link_corrections_are_audited_without_reversing_asset_accounting` | PASS |
| `test_link_uses_full_value_without_posting_or_changing_service_item` | PASS |
| `test_migration_archives_full_shared_link_without_rewriting_asset` | PASS |
| `test_native_depreciation_and_reversal_are_live_without_crane_save` | PASS |
| `test_no_company_ownership_disallows_even_third_party_asset_links` | PASS |
| `test_zero_company_shared_interest_keeps_partners_but_no_asset` | PASS |

## TestRentalWorkflow

| Test method / business scenario | Original result |
|---|---|
| `test_assignment_defaults_use_settings_and_crane_prices` | PASS |
| `test_assignment_first_and_timesheet_first` | PASS |
| `test_completed_maintenance_uses_shared_expense_entry` | PASS |

## TestCraneProfitSettlement

| Test method / business scenario | Original result |
|---|---|
| `test_agreement_validation_and_operator_arrangements` | PASS |
| `test_changed_percentages_are_dated_and_historical_snapshots_survive` | PASS |
| `test_closed_sources_and_backdated_postings_are_protected` | PASS |
| `test_company_can_receive_both_operating_share_and_residual` | PASS |
| `test_corrected_profit_split_creates_partner_payable` | PASS |
| `test_denied_journal_creation_rolls_back_settlement` | PASS |
| `test_duplicate_drafts_cannot_both_submit_and_gaps_are_rejected` | PASS |
| `test_expenses_over_balance_block_save_and_submission` | PASS |
| `test_external_operator_receives_operating_and_residual_in_one_payable` | PASS |
| `test_grand_total_allocation_includes_tax_without_duplicating_other_cranes` | PASS |
| `test_invalid_historical_expense_blocks_settlement` | PASS |
| `test_large_partner_journal_posts_and_reverses_in_the_same_transaction` | PASS |
| `test_many_partners_and_dated_pause` | PASS |
| `test_migration_is_repeatable_and_leaves_legacy_cranes_unconfigured` | PASS |
| `test_multiple_source_income_accounts_returns_and_dimensions` | FAIL |
| `test_native_invoice_attribution_and_missing_accounting_permissions` | PASS |
| `test_native_tagged_invoices_and_journals_are_counted_once` | PASS |
| `test_negative_revenue_stops_new_period` | PASS |
| `test_operated_for_owner_rejects_company_rows_even_without_ownership` | PASS |
| `test_operating_fee_survives_zero_residual_but_one_cent_deficit_blocks` | PASS |
| `test_operating_first_does_not_require_legacy_allocation_account` | PASS |
| `test_operating_first_single_owner_without_company_in_partner_table` | PASS |
| `test_operating_percentage_rejects_invalid_and_nonfinite_values` | PASS |
| `test_operating_percentage_versions_and_legacy_migration_preserve_history` | PASS |
| `test_owner_zero_profit_requires_explicit_confirmation` | PASS |
| `test_posting_independent_shares_and_native_partial_payments` | PASS |
| `test_signed_income_account_allocation_and_invalid_account_rejection` | PASS |
| `test_switching_owner_operation_to_shared_still_requires_new_effective_date` | PASS |
| `test_zero_profit_and_rounding_conserve_the_distributed_amount` | PASS |

## TestCraneTimesheet

| Test method / business scenario | Original result |
|---|---|
| `test_assignment_and_explicit_terms_override_settings` | PASS |
| `test_distinct_worked_hours_include_overnight_and_ignore_idle_dates` | PASS |
| `test_invoice_posting_units_payments_and_cancellation` | PASS |
| `test_new_timesheet_defaults_create_assignment_and_preserve_snapshot` | PASS |
| `test_owned_crane_never_creates_purchase_invoice` | PASS |
| `test_paid_invoice_is_not_offered_for_payment` | PASS |
| `test_periods_can_overlap_but_worked_shifts_cannot` | PASS |
| `test_purchase_permissions_are_required` | PASS |
| `test_removed_manual_terms_are_archived_without_repricing` | SKIP |
| `test_supplier_day_and_month_use_worked_dates_not_period_span` | PASS |
| `test_supplier_terms_and_invoice_link_are_validated` | PASS |
| `test_unchecked_rented_skips_purchase_and_survives_saves` | PASS |
| `test_uom_migration_preserves_existing_terms_and_settings` | PASS |
| `test_worked_hour_migration_preserves_history_and_resets_daily_draft_rate` | PASS |

## TestTreasuryTransaction

| Test method / business scenario | Original result |
|---|---|
| `test_bank_to_cash` | PASS |
| `test_cost_center_validation_and_journal_attribution` | PASS |
| `test_journal_permission_failure_rolls_back_submission` | PASS |
| `test_party_is_copied_to_destination_journal_row` | PASS |
| `test_party_on_designated_balance_accounts` | PASS |
| `test_payment_mode_requires_enabled_company_cash_or_bank_account` | PASS |
| `test_post_reverse_and_amend` | PASS |
| `test_reject_invalid_amount_accounts_and_manual_journal` | PASS |
| `test_reject_invalid_or_incomplete_party` | PASS |

## TestCraneRentalProfitability

| Test method / business scenario | Original result |
|---|---|
| `test_cancelled_and_draft_expenses_and_sales_return` | PASS |
| `test_historical_expenses_with_missing_or_unsubmitted_journals` | PASS |
| `test_posted_income_cash_custody_and_repeatable_demo` | PASS |
| `test_required_filters_and_permissions` | PASS |
| `test_shared_invoice_link_is_counted_once_and_purchase_is_included` | PASS |

## TestCraneConnections

| Test method / business scenario | Original result |
|---|---|
| `test_child_assignments_and_invoice_header_and_rows_are_unioned` | PASS |
| `test_parts_payments_follow_only_unshared_company_cost_center` | PASS |
| `test_payments_follow_asset_and_invoice_references_without_duplicates` | PASS |
| `test_scalar_asset_link_empty_links_and_site_dimensions` | PASS |
| `test_source_permission_is_required` | PASS |
| `test_target_permissions_and_unrequested_doctypes` | PASS |

## TestDistributionReporting

| Test method / business scenario | Original result |
|---|---|
| `test_company_operating_residual_cost_burden_and_source_breakdown` | PASS |
| `test_dashboard_reconciles_report_and_scopes_status_counts` | PASS |
| `test_denied_sources_or_payment_documents_fail_instead_of_partial_totals` | PASS |
| `test_drafts_are_separate_estimates_and_reporting_does_not_recalculate` | PASS |
| `test_mixed_posted_and_draft_totals_and_non_cash_adjustments_stay_separate` | PASS |
| `test_one_cent_cost_burden_matches_actual_rounded_residual_difference` | PASS |
| `test_partial_future_payment_as_of_movements_and_cancellation` | PASS |
| `test_shared_invoice_and_partner_filter_do_not_duplicate_settlement_totals` | PASS |
| `test_snapshot_percentages_and_independent_ownership_and_profit` | PASS |
| `test_work_overlap_posting_date_assignment_customer_and_status_filters` | PASS |

## TestExpenseParties

| Test method / business scenario | Original result |
|---|---|
| `test_amendment_does_not_clear_unrelated_journal` | PASS |
| `test_backfill_is_idempotent_and_preserves_amounts` | PASS |
| `test_backfill_preserves_conflicting_party` | PASS |
| `test_cancel_amend_creates_fresh_journal` | PASS |
| `test_employee_on_journal_with_native_ledger_and_cancellation` | PASS |
| `test_expense_without_employee` | PASS |
| `test_unrelated_journal_keeps_native_party_validation` | FAIL |

## TestNativeCraneWorkflow

| Test method / business scenario | Original result |
|---|---|
| `test_capital_improvement_uses_actual_stock_value_and_reverses_together` | PASS |
| `test_custody_crane_can_consume_stock_but_cannot_capitalize` | PASS |
| `test_external_service_costs_and_capitalization_are_not_duplicated` | PASS |
| `test_improvement_regenerates_native_depreciation_schedule` | PASS |
| `test_migration_repeat_does_not_change_new_terms_or_post_ledgers` | PASS |
| `test_native_permission_and_attribution_checks` | PASS |
| `test_owner_recovery_consumes_parts_and_is_not_rental_profit` | PASS |
| `test_repair_costs_appear_in_posting_date_profitability` | PASS |
| `test_review_settlement_includes_repair_and_posts_selected_expense` | FAIL |
| `test_serialized_improvement_restores_stock_on_cancellation` | PASS |
| `test_shared_item_keeps_two_cranes_separate_on_one_invoice` | PASS |
| `test_shared_service_product_and_company_interest_values` | PASS |
| `test_stock_repair_expenses_once_without_increasing_asset` | PASS |

## TestPartnerSettlements

| Test method / business scenario | Original result |
|---|---|
| `test_automatic_submission_and_shareholder_payments` | PASS |
| `test_automation_and_reports_keep_accounting_permissions` | PASS |
| `test_cancel_combined_partner_payment_keeps_other_settlement` | PASS |
| `test_cancel_expense_includes_payments_and_native_amendments` | PASS |
| `test_cancel_invoice_includes_customer_receipt` | PASS |
| `test_cancel_scope_changes_and_permission_denial` | PASS |
| `test_cancel_settlement_preserves_invoice_and_work` | PASS |
| `test_cancel_shared_expense_cancels_all_affected_settlements` | PASS |
| `test_combined_partner_payment_from_open_entitlements` | PASS |
| `test_confirmed_cancel_all_from_invoice_and_timesheet` | PASS |
| `test_deficit_rolls_back_invoice_and_entitlements` | PASS |
| `test_expense_work_terms_validate_and_company_matches` | PASS |
| `test_late_assignment_expense_is_allocated_only_once_by_worked_hours` | PASS |
| `test_maintenance_rental_context_carries_to_expense` | FAIL |
| `test_migration_preserves_historical_journals_and_snapshots` | PASS |
| `test_open_entitlements_permissions_and_account_scope` | PASS |
| `test_overlapping_work_period_costs_are_allocated_once` | PASS |
| `test_payment_allocator_keeps_native_non_settlement_behavior` | PASS |
| `test_payment_form_reallocates_partial_shareholder_payment` | PASS |
| `test_payment_link_validation_and_historical_report_date` | PASS |
| `test_period_expense_rounding_and_consecutive_closure` | PASS |
| `test_period_expense_service_proration` | PASS |
| `test_rental_context_requires_selection_and_timesheet_cost_is_direct` | PASS |
| `test_restore_migration_is_dated_idempotent_and_preserves_posted_snapshots` | PASS |
| `test_service_dates_and_assignment_isolate_expenses` | PASS |
| `test_settled_timesheet_is_immutable_and_duplicate_is_rejected` | PASS |
| `test_shared_invoice_allocates_once_and_reports_real_movements` | PASS |
| `test_shareholder_selection_supersedes_hidden_supplier_aliases` | PASS |

## TestRentalItemDefaults

| Test method / business scenario | Original result |
|---|---|
| `test_draft_invoice_account_stays_local_to_demo` | FAIL |
| `test_existing_default_is_preserved_on_failure` | PASS |

## TestTreasuryWorkbook

| Test method / business scenario | Original result |
|---|---|
| `test_cost_center_filter_opening_export_and_backfill` | PASS |
| `test_failed_posting_rolls_back_whole_import` | PASS |
| `test_parser_dates_and_formula_only_rows` | PASS |
| `test_post_reconcile_repeat_export_and_cancel` | PASS |
| `test_reject_unsafe_amounts_formulas_and_changed_file` | PASS |
| `test_report_opening_period_permissions_and_wrong_company` | PASS |
