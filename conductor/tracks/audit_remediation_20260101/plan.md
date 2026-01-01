# Plan: Audit Remediation 2026-01-01

## Phase 1: Metadata & Catalog Cleanup
- [x] Task: Update `scripts/cleanup_metadata_catalog.py` to inject `FOREX` metadata. 152f628
    - [ ] Sub-task: Define `FOREX` metadata constants.
    - [ ] Sub-task: Add logic to check for `FOREX` in `ExchangeCatalog` and upsert if missing.
- [x] Task: Refine SCD Type 2 logic in `scripts/cleanup_metadata_catalog.py`. 44f8479
    - [ ] Sub-task: Implement `resolve_scd_duplicates(df)` function.
    - [ ] Sub-task: Ensure strict sorting by `symbol` and `updated_at`.
    - [ ] Sub-task: Apply `valid_until` to historical records based on the next record's timestamp.
    - [ ] Sub-task: Verify only one active record per symbol.
- [x] Task: Run `scripts/cleanup_metadata_catalog.py` to apply changes. 152f628
    - [ ] Sub-task: Verify output logs for "Duplicates removed" vs "Duplicates archived".

## Phase 2: Coverage Analysis & Verification
- [x] Task: Run `scripts/comprehensive_audit.py` to verify remediation. 7fde571
    - [ ] Sub-task: Confirm `FOREX` exchange is no longer missing.
    - [ ] Sub-task: Confirm "Symbols with duplicates" metric (should be 0 active duplicates, or audit script updated to count only active duplicates).
- [x] Task: Analyze Coverage Score. fcee52b
    - [ ] Sub-task: Review `calculate_coverage_score` logic in `scripts/comprehensive_audit.py`.
    - [ ] Sub-task: Identify missing categories (e.g., Options, Bonds).
    - [ ] Sub-task: Write `docs/research/coverage_gap_analysis_2026.md` with findings.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)
