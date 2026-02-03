---
title: "refactor: Migrate research scripts from Pickle to Parquet and DataLoader"
type: refactor
date: 2026-02-03
---

# refactor: Migrate research scripts from Pickle to Parquet and DataLoader

## Overview

This plan outlines the systematic migration of 70+ research scripts and data artifacts from the insecure `pickle` format to `parquet`, ensuring compliance with the institutional `DataLoader` standard established in PR #5. This is the final step to close the RCE vulnerability window and ensure data pipeline robustness.

## Problem Statement / Motivation

1.  **Security Risk**: The repository still contains 70+ scripts using `pd.read_pickle`, representing a potential Remote Code Execution (RCE) vector if artifacts are compromised.
2.  **Inconsistency**: The core engine now writes Parquet, but downstream analysis scripts expect Pickle, causing workflow breakage.
3.  **Technical Debt**: Inline file path construction (e.g. `f"data/runs/{run_id}/returns.pkl"`) is brittle and bypasses the `DataLoader`'s path resolution logic.

## Proposed Solution

1.  **Mass Artifact Conversion**:
    -   Implement a parallelized migration utility (`scripts/maintenance/migrate_pickle_to_parquet.py`) to convert all existing `data/**/*.pkl` artifacts to `.parquet`.
    -   **Constraint**: Use a Docker sandbox or strictly isolated environment for the one-time conversion to mitigate RCE risk during the process.

2.  **Script Refactoring**:
    -   Systematically refactor all scripts in `scripts/` to use `tradingview_scraper.data.loader.DataLoader`.
    -   **Ban**: `pd.read_pickle` AND direct `pd.read_parquet`.
    -   **Enforce**: Usage of `loader.load_run_data()` or `loader.ensure_safe_path()`.

3.  **DataLoader Hardening**:
    -   Update `DataLoader` to emit a `DeprecationWarning` when falling back to Pickle.
    -   Eventually remove Pickle support entirely (Phase 2).

## Technical Considerations

-   **Data Consistency**:
    -   **MultiIndex**: Parquet flattens MultiIndexes. The `DataLoader` MUST reconstruct the `(Date, Symbol)` index upon loading.
    -   **Timezones**: Parquet handles timezones strictly. We must apply `ensure_utc_index` immediately after loading.
-   **Non-DataFrame Objects**: Some pickles might be `dict` or `list` (metadata). These must be migrated to `.json`, not `.parquet`.

## Acceptance Criteria

- [ ] All `data/**/*.pkl` files containing DataFrames are converted to `.parquet`.
- [ ] All `data/**/*.pkl` files containing metadata/dicts are converted to `.json`.
- [ ] No `pd.read_pickle` calls remain in `scripts/`.
- [ ] All research scripts run successfully against the new Parquet artifacts.
- [ ] `DataLoader` handles MultiIndex reconstruction transparently.

## Success Metrics

-   **Security**: 0 instances of `pd.read_pickle` in the codebase.
-   **Performance**: Storage footprint reduced by >60% (Parquet compression).
-   **Stability**: 100% of regression tests pass.

## Dependencies & Risks

-   **Risk**: Custom Python objects in pickles will fail to convert.
    -   *Mitigation*: Log failures and require manual intervention for complex objects.
-   **Risk**: "Poisoned" historical pickles executing code during migration.
    -   *Mitigation*: Run migration script in a network-isolated container.

## References & Research

-   **Institutional Standard**: `AGENTS.md` Section 11.
-   **Previous Plan**: `docs/plans/2026-02-02-refactor-backtest-remediation-plan-deepened.md`.
-   **Security Audit**: `docs/solutions/security-issues/path-traversal-hardening-SecurityUtils-20260201.md`.

## Implementation Phases

### Phase 1: Artifact Migration Utility (P1)
- [ ] Create `scripts/maintenance/migrate_pickle_to_parquet.py`.
- [ ] Implement `joblib` parallel processing.
- [ ] Implement schema validation (DataFrame vs Dict check).
- [ ] Execute conversion on local environment (Sandboxed).

### Phase 2: Script Refactoring (P2)
- [ ] Refactor `scripts/research/*.py` to use `DataLoader`.
- [ ] Refactor `scripts/archive/*.py` (or archive/delete if obsolete).
- [ ] Update `quant-backtest` skill to reference Parquet paths.

### Phase 3: Validation & Cleanup (P2)
- [ ] Verify `features_matrix` MultiIndex integrity.
- [ ] Delete legacy `.pkl` files after verification.
