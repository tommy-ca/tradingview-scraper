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
- [x] **CVXPortfolio Missing-Returns Warnings**: Resolve missing-values/universe drift.
  - **Status**: Audit Validated (Run 20260103-223836). Applied `fillna(0.0)` and index alignment; `12_validation.log` confirms zero warnings.
- [x] **Institutional Fidelity (Jan 2026) - Bug Fixes**:
  - [x] **Simulator Truncation (20-day limit)**: Fixed. Run `20260103-223836` confirms full depth (2024-08 to 2026-01).
  - [x] **VectorBT Lookahead Bias**: Fixed. Removed `shift(-1)`; verified parity with other simulators.
  - [x] **ECI Volatility Defaults**: Fixed. Standardized on 0.5% daily default.

## Snapshot: Run 20260103-235511
- Completed `make flow-production PROFILE=production RUN_ID=20260103-235511`; validated the new structured artifact hierarchy and unified taxonomy.
- `INDEX.md` successfully summarizes top performers using only the official `market`, `benchmark`, and `raw_pool_ew` baselines.
- `audit.jsonl` contains full context blocks for all optimization and simulation steps.

## Universe & Baseline Definitions
- **Canonical universe (raw pool)**: The unioned discovery output (`portfolio_candidates_raw.json`) and its aligned returns (`portfolio_returns_raw.pkl`) produced by `make data-prep-raw`.
- **Natural-selected universe**: The selection winners in `portfolio_candidates.json` that are passed to the downstream engines (`data/lakehouse/portfolio_returns.pkl`).
- **`market`**: (Standard) Equal weight over `settings.benchmark_symbols` (SPY). noise-free institutional hurdle.
- **`benchmark`**: (Standard) Equal weight over the Natural-Selected universe. The risk-profile comparator.
- **`raw_pool_ew`**: (Diagnostic) Selection-alpha baseline that re-weights the raw pool (excluding benchmark symbols).

## Current Focus
- **Taxonomy Enforcement**: Ensure all reporting and tournament tools adhere to the `market`, `benchmark`, `raw_pool_ew` standard.
- **Continuous Monitoring**: Monitor the newly integrated metadata gate and fidelity checks in automated runs.
- **Guardrail sentinel readiness**: Keep canonical and selected guardrail pairs re-run quarterly.

## Next Steps Tracker
- [x] **Phase 3: Directory Restructuring**: Audit Validated (Run `20260103-235511`).
- [x] **Phase 4: Script Audit & Cleanup**: Completed. Categorized and archived 110+ scripts.
- **Metadata gate**: Gate satisfied for `20260103-235511` (100% coverage).

## Status Sync
- **Artifact Reorganization**: Audit Validated (Run `20260103-235511`).
- **Metadata gate**: Satisfied—Run `20260103-235511` recorded 100% coverage.
- **Selection report**: Completed—Run `20260103-235511` confirmed restoration of selection story.
- **CVXPortfolio warnings**: Completed—Run `20260103-235511` confirmed zero warnings.
- **Guardrail sentinel**: Completed—Run `20260103-235511` passed invariance check.
- **Health audit**: Completed for run `20260103-235511` (100% healthy).

## Script Audit & Cleanup Roadmap (Jan 2026)
### 1. Categorization Tiers
- **Tier 1 (Core)**: ~30 scripts in `scripts/` root (e.g., `backtest_engine.py`, `natural_selection.py`).
- **Tier 2 (Maintenance)**: Diagnostic/Utility tools in `scripts/maintenance/`.
- **Tier 3 (Research)**: Active prototypes in `scripts/research/`.
- **Tier 4 (Archive)**: Legacy/Redundant scripts in `scripts/archive/`.
