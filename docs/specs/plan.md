# Plan: Benchmark Baseline & Selection Specs

## Objectives
- **Baseline stability**: Ensure `market`, `benchmark`, and `raw_pool_ew` are deterministic and usable as backtest baselines for risk profiles.
- **Selection specs alignment**: Keep selection-mode behavior isolated from baselines when the universe source is unchanged.
- **Workflow guardrails**: Enforce metadata coverage, baseline invariance checks, and report integrity as first-class pipeline steps.

## Context: Recently Completed
- [x] **Baseline Taxonomy Decommissioning**: Removed legacy `market_baseline` and `benchmark_baseline` aliases in favor of standardized `market`, `benchmark`, and `raw_pool_ew`.
  - **Audit Validated**: `scripts/backtest_engine.py` and `scripts/generate_reports.py` now use the unified taxonomy. Research scripts and audits have been aligned.
- [x] **Selection Metadata Enrichment**: `scripts/enrich_candidates_metadata.py` now automatically detects and enriches the full returns universe with institutional defaults (`tick_size`, `lot_size`, etc.).
- [x] **Audit Ledger Hashing**: `tradingview_scraper/utils/audit.py` now handles mixed-type DataFrames (strings/floats) correctly.
- [x] **CVXPortfolio Simulator Fidelity**: Strictly aligned weight indices with rolling returns and standardized on `cash` modeling to prevent solver crashes.
- [x] **Dynamic Strategy Resume**: `scripts/generate_reports.py` now automatically identifies and highlights the best engine per profile in the strategy resume.
- [x] **Regime-Specific Attribution**: Fixed data loading priority in `generate_reports.py` to ensure window-level regime metrics are captured from `tournament_results.json`.
- [x] **Atomic & Safe Audit Writes**: Implemented Unix file locking (`fcntl`) in `scripts/natural_selection.py` to prevent corruption of the shared `selection_audit.json`.
- [x] **Settings Precedence Clarified**: CLI init overrides now take priority, followed by `.env`, OS env, manifest profile, manifest defaults, then code defaults.
- [x] **Metadata Catalog Drift (Veto Cascade)**: Missing `tick_size`, `lot_size`, and `price_precision` metadata forces repeated vetoes and destabilizes HRP distances.
  - **Status**: Audit Validated (Run 20260103-223836). Enrichment keeps candidate manifests complete, and the coverage gate is enforced via `scripts/metadata_coverage_guardrail.py`.
- [x] **Selection Report Generator Missing Entry Point**: Restoration of `generate_selection_report`.
  - **Status**: Audit Validated (Run 20260103-223836). Fixed signature and confirmed `selection_audit.md` (and new `selection_report.md` path) are populated in run artifacts.
- [x] **CVXPortfolio Missing-Returns Warnings**: Resolved universe drift and auto-injected cash column alignment.
  - **Status**: Audit Validated (Run 20260104-005636). Explicit cash column injection and `h_init` alignment ensures clean `cvxportfolio` execution across dynamic universes. Verified in 4D tournament log.
- [x] **Institutional Fidelity (Jan 2026) - Bug Fixes**:
  - [x] **Simulator Truncation (20-day limit)**: Fixed. Run `20260103-223836` confirms full depth (2024-08 to 2026-01).
  - [x] **VectorBT Lookahead Bias**: Fixed. Removed `shift(-1)`; verified parity with other simulators.
  - [x] **ECI Volatility Defaults**: Fixed. Standardized on 0.5% daily default.
- [x] **Scalability Architectural Design**: Defined the transition to Ray/Prefect/SkyPilot stack in `docs/specs/mlops_scalability_v1.md`.

## Current Focus
- **MLOps Scalability Pivot (Phase 6)**: Transition to Ray (Compute) and Prefect (Orchestration) to eliminate execution bottlenecks and focus on Alpha Core per `docs/specs/mlops_scalability_v1.md`.
- **4D Tournament Validation**: Audit and finalize results from the Grand 4D Tournament.
- **Guardrail sentinel readiness**: Keep canonical and selected guardrail pairs re-run quarterly.

## Next Steps Tracker
- [ ] **Phase 6: MLOps Integration**: Refactor backtest units into atomized tasks; integrate Ray shared object store.
- [ ] **Phase 5: Performance Optimization**: Implement multiprocessing/Ray logic in `Grand4DTournament`.
- [x] **Phase 3: Directory Restructuring**: Audit Validated (Run `20260103-235511`).

- [x] **Phase 4: Script Audit & Cleanup**: Completed. Categorized and archived 110+ scripts.
- **Metadata gate**: Gate satisfied for `20260103-235511` (100% coverage).

## Status Sync
- **Artifact Reorganization**: Audit Validated (Run `20260103-235511`).
- **4D Tournament Validation**: In Progress (Run `20260104-005636`). Initial results for `v2.1 / window` confirm high-fidelity simulator parity and significant optimization alpha.
- **Metadata gate**: Satisfied—Run `20260104-005636` recorded 100% coverage.
- **Selection report**: Completed—Confirmed restoration of selection story in run artifacts.
- **CVXPortfolio warnings**: Resolved—Run `20260104-005636` confirms zero "universe mismatch" warnings in tournament logs.
- **Guardrail sentinel**: Completed—Passed invariance check against previous baseline.
- **Health audit**: Completed for latest production run (100% healthy).


## Script Audit & Cleanup Roadmap (Jan 2026)
### 1. Categorization Tiers
- **Tier 1 (Core)**: ~30 scripts in `scripts/` root (e.g., `backtest_engine.py`, `natural_selection.py`).
- **Tier 2 (Maintenance)**: Diagnostic/Utility tools in `scripts/maintenance/`.
- **Tier 3 (Research)**: Active prototypes in `scripts/research/`.
- **Tier 4 (Archive)**: Legacy/Redundant scripts in `scripts/archive/`.

### 2. Implementation Plan (Atomic Commits)
1.  **Skeleton**: Create subdirectories with `__init__.py`. (Completed)
2.  **Maintenance**: Move utility tools. (Completed)
3.  **Research**: Move prototypes. (Completed)
4.  **Archive**: Move legacy scripts. (Completed)
5.  **Verification**: Confirm `make flow-production` and tests still pass with clean root. (Completed)

### 3. Detailed Migration Manifest
| Target Directory | Scripts to Migrate |
| :--- | :--- |
| `scripts/maintenance/` | `cleanup_metadata_catalog`, `update_index_lists`, `track_portfolio_state`, etc. |
| `scripts/research/` | `analyze_forex_universe`, `subcluster`, `benchmark_risk_models`, `explore_*`, `proto_*`, `research_*`, `tune_*`, etc. |
| `scripts/archive/` | `run_e2e_v1`, `run_grand_tournament`, `summarize_results`, `verify_phase*`, `debug_*`, `test_*`, etc. |

## Risk Profile Matrix
| Profile | Category | Universe | Weighting / Optimization | Notes |
| --- | --- | --- | --- | --- |
| `market` | Baseline | Benchmark symbols (`settings.benchmark_symbols`) | Equal-weight long-only allocation; no optimizer, no clusters | Institutional hurdle; logged identically across engines (`market_profile_unification`). |
| `benchmark` | Baseline | Natural-selected universe | Asset-level equal weight over the winners; no clustering | Research baseline; logs universe source + count for every run so alpha deltas are traceable. |
| `raw_pool_ew` | Selection-alpha baseline | Canonical or selected | Asset-level equal weight across the raw pool, excludes benchmark symbols | Diagnostic only until coverage + invariance pass; record `raw_pool_symbol_count` and hash per window. |
| `equal_weight` | Risk profile | Natural-selected universe | Hierarchical equal weight (cluster-level HE + HERC 2.0 intra) | Neutral, low-friction profile used for volatility-neutral comparisons. |
| `min_variance` | Risk profile | Natural-selected universe | Cluster-level minimum variance (solver-driven) | Defensive, low-volatility target; guardrails ensure `HERC 2.0` intra weighting. |
| `hrp` | Risk profile | Natural-selected universe | Hierarchical risk parity (HRP) | Structural risk-parity baseline for regime robustness; uses cluster distances tuned by metadata. |
| `max_sharpe` | Risk profile | Natural-selected universe | Cluster-level max Sharpe mean-variance | Growth regime focus; exposures are clamped by cluster caps before solver execution. |
| `barbell` | Strategy profile | Natural-selected universe | Core HRP sleeve + aggressor sleeve | Convexity-seeking profile that combines core stability with an antifragility-driven tail sleeve. |
