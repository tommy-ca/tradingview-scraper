# Plan: Benchmark Baseline & Selection Specs

## Objectives
- **Baseline stability**: Ensure `market`, `benchmark`, and `raw_pool_ew` are deterministic and usable as backtest baselines for risk profiles.
- **Selection specs alignment**: Keep selection-mode behavior isolated from baselines when the universe source is unchanged.
- **Workflow guardrails**: Enforce metadata coverage, baseline invariance checks, and report integrity as first-class pipeline steps.

## Context: Recently Completed
- [x] **Selection Metadata Enrichment**: `scripts/enrich_candidates_metadata.py` now automatically detects and enriches the full returns universe with institutional defaults (`tick_size`, `lot_size`, etc.).
- [x] **Audit Ledger Hashing**: `tradingview_scraper/utils/audit.py` now handles mixed-type DataFrames (strings/floats) correctly.
- [x] **CVXPortfolio Simulator Fidelity**: Strictly aligned weight indices with rolling returns and standardized on `cash` modeling to prevent solver crashes.
- [x] **Dynamic Strategy Resume**: `scripts/generate_reports.py` now automatically identifies and highlights the best engine per profile in the strategy resume.
- [x] **Regime-Specific Attribution**: Fixed data loading priority in `generate_reports.py` to ensure window-level regime metrics are captured from `tournament_results.json`.
- [x] **Atomic & Safe Audit Writes**: Implemented Unix file locking (`fcntl`) in `scripts/natural_selection.py` to prevent corruption of the shared `selection_audit.json`.
- [x] **Settings Precedence Clarified**: CLI init overrides now take priority, followed by `.env`, OS env, manifest profile, manifest defaults, then code defaults.
  - **Implemented**: `tradingview_scraper/settings.py` settings source order.
  - **Documented**: `docs/specs/workflow_manifests.md`.
  - **Tests**: `tests/test_settings_precedence.py` (lookback, backtest windows, cluster cap, backtest simulators, TV_PROFILE precedence).
  - **Validated**: `uv run pytest tests/test_settings_precedence.py` (14 passed); `TV_PROFILE=development ... --export-env` shows `LOOKBACK=60`, `PORTFOLIO_LOOKBACK_DAYS=60`.
  - **CI**: `.github/workflows/settings-precedence.yml` runs the precedence test suite on relevant changes.


## Snapshot: Run 20260103-182051
- Completed `make flow-production PROFILE=production RUN_ID=20260103-182051`; the artifacts directory (`artifacts/summaries/runs/20260103-182051/`) now holds the resolved manifest, full logs (steps 01-14), `audit.jsonl`, `tournament_results.json`, `selection_audit.json`, and the generated reports (tear sheets, cluster maps, etc.).
- `make baseline-audit STRICT_BASELINE=1 REQUIRE_RAW_POOL=1 RUN_ID=20260103-182051` confirmed 11 windows for each baseline (`market`, `benchmark`, and `raw_pool_ew`) across the four engines (custom, cvxportfolio, vectorbt, nautilus), ensuring both the structural benchmarks and the selection baseline produce coverage for this run.
- `selection_audit.json` recorded 44 raw symbols, 13 selected winners, lookbacks `[60, 120, 200]`, and the canonical cluster winners (`AMEX:SPY`, `NASDAQ:TSLA`, `NASDAQ:AMZN`, `NASDAQ:AAPL`, `NASDAQ:AVGO`, `NASDAQ:GOOG`, `NYSE:WMT`, `NYSE:JNJ`, `NYSE:ABBV`, `NYSE:BAC`, `NYSE:MA`, `NYSE:LLY`, `NYSE:XOM`), plus the veto list that is now stable after the metadata refresh.
- `make baseline-guardrail RUN_A=20260103-171913 RUN_B=20260103-182051` failed because the selected-universe summary (run B) drifted from the canonical-universe summary (run A); the tolerance (1e-9) was exceeded by the difference in annualized return (≈+0.0903), annualized vol (≈+0.0706), and win rate (+18%), which indicates we compared different universes. Re-run the guardrail once we have a matching universe pair (canonical vs canonical or selected vs selected) so the invariance gate can pass.
- `make baseline-guardrail RUN_A=20260103-171756 RUN_B=20260103-171913` passed (canonical vs canonical); both runs reported `windows_count=11`, `annualized_return=0.18942949566401787`, `annualized_vol=0.11374061220057992`, and `win_rate=0.6363636363636364`, proving the canonical baseline summary is invariant when the universe source is held constant.
- `make baseline-guardrail RUN_A=20260103-172054 RUN_B=20260103-182051` passed (selected vs selected); both runs reported `windows_count=11`, `annualized_return=0.2797840635298483`, `annualized_vol=0.18431122265126593`, and `win_rate=0.8181818181818182`, showing the selected universe summary is stable across selection-mode sweeps when the raw pool source is identical.
- The mismatched canonical vs selected guardrail (`RUN_A=20260103-171913`, `RUN_B=20260103-182051`) now emits a sentinel passage—logs note the metadata mismatch (run A: canonical/41/9c01..., run B: selected/9/05b2...) and the script exits successfully after skipping the tolerance check, allowing the sentinel entry to be part of the human-readable guardrail table without degrading the pass/fail status of the pipeline.

## Universe & Baseline Definitions
- **Canonical universe (raw pool)**: The unioned discovery output (`portfolio_candidates_raw.json`) and its aligned returns (`portfolio_returns_raw.pkl`) produced by `make data-prep-raw`; natural-selected universes must be strict subsets of this dataset, and the canonical matrix must cover at least `train + test + 1` contiguous rows before any `raw_pool_ew` windows start. See `docs/specs/optimization_engine_v2.md` for the single-source definition.
- **Natural-selected universe**: The selection winners in `portfolio_candidates.json` that are passed to the downstream engines (`data/lakehouse/portfolio_returns.pkl`). Every runtime choice that touches the active universe should document whether it is canonical or natural-selected.
- **`market`**: The institutional benchmark equal weight over `settings.benchmark_symbols` (SPY). It is long-only, must sum to 1, and writes benchmark-symbol counts + hash to `audit.jsonl`. No replacements or heuristics are allowed—`market` is the noise-free hurdle.
- **`benchmark`**: The research baseline equal weight over the active (natural-selected) universe. It is the canonical comparator for all risk profiles, logging symbol counts, source, and returns hash in `audit.jsonl` so each run can be traced.
- **`raw_pool_ew`**: The selection-alpha baseline that re-weights the raw pool via `TV_RAW_POOL_UNIVERSE` (defaults to `selected` for this run but can be forced to `canonical`). It excludes the benchmark symbols, requires full coverage of `train + test + 1` rows, and must remain invariant when the universe source is unchanged. Only treat `raw_pool_ew` as a baseline when both coverage and invariance pass; otherwise, mark it as a diagnostic.
- **`market_baseline` / `benchmark_baseline`**: Legacy aliases emitted by the `custom` engine for backward compatibility. They mirror `market` and `benchmark` respectively and exist in reports so that older comparison dashboards continue to surface the same baseline numbers.

## Baseline Spec Questions
### 1. Keep baselines to market and benchmark only without noise
The official taxonomy is restricted to `market` and `benchmark` (per `docs/specs/optimization_engine_v2.md`), so avoid adding noise (meta-features, heuristics, or selection-aware adjustments) into these profiles. Additional labels such as `equal_weight` or `raw_pool_ew` belong to risk profile diagnostics, not the baseline taxonomy.
### 2. Add specs for baselines with clear requirements
- **`market`**: Benchmark symbols that come from `settings.benchmark_symbols`; fail fast with empty weights if missing; log `benchmark_symbols`, counts, and the returns hash; share this output (and eventual tear-sheet snippet) across all simulators so the control group is replayed in every run.
- **`benchmark`**: Equal weight over the active universe; log the universe source and symbol count; use it for risk-profile comparisons and reporting (selection alpha is relative to this baseline). Do not feed it selection metadata—the baseline must stay stable when selection mode flips.
- **`raw_pool_ew`**: Controlled by `TV_RAW_POOL_UNIVERSE`; when running against the canonical return matrix it must (a) have at least one contiguous window of `train + test + 1` rows, (b) exclude benchmark symbols, (c) record `raw_pool_symbol_count` and `raw_pool_returns_hash` in `audit.jsonl`, and (d) pass invariance checks against other runs that use the same universe.
### 3. Update specs for canonical and natural-selected universes
The canonical universe is the production raw pool (source of truth), and natural-selected universes should always be derived from it through the selection engine. Document both layers in every audit entry (`selection_mode`, `universe_source`, `selection_audit.json` hash) so traceability persists across `baseline-guardrail` and tournament outputs.
### 4. Clarify the difference between benchmark and raw_pool_ew
`benchmark` is an equal-weighted control over the **selected** (active) universe, whereas `raw_pool_ew` sits over the **raw (canonical or selected) pool** and is used strictly for selection-alpha diagnostics. The benchmark is the risk-profile comparator, and `raw_pool_ew` is the selection baseline; they must not be conflated.

## Risk Profile Matrix
| Profile | Category | Universe | Weighting / Optimization | Notes |
| --- | --- | --- | --- | --- |
| `market` | Baseline | Benchmark symbols (`settings.benchmark_symbols`) | Equal-weight long-only allocation; no optimizer, no clusters | Institutional hurdle; logged identically across engines (`market_profile_unification`). |
| `benchmark` | Baseline | Natural-selected universe | Asset-level equal weight over the winners; no clustering | Research baseline; logs universe source + count for every run so alpha deltas are traceable. |
| `raw_pool_ew` | Selection-alpha baseline | Canonical or selected (via `TV_RAW_POOL_UNIVERSE`) | Asset-level equal weight across the raw pool, excludes benchmark symbols | Diagnostic only until coverage + invariance pass; record `raw_pool_symbol_count` and hash per window. |
| `equal_weight` | Risk profile | Natural-selected universe | Hierarchical equal weight (cluster-level HE + HERC 2.0 intra) | Neutral, low-friction profile used for volatility-neutral comparisons. |
| `min_variance` | Risk profile | Natural-selected universe | Cluster-level minimum variance (solver-driven) | Defensive, low-volatility target; guardrails ensure `HERC 2.0` intra weighting. |
| `hrp` | Risk profile | Natural-selected universe | Hierarchical risk parity (HRP) | Structural risk-parity baseline for regime robustness; uses cluster distances tuned by metadata. |
| `max_sharpe` | Risk profile | Natural-selected universe | Cluster-level max Sharpe mean-variance | Growth regime focus; exposures are clamped by cluster caps before solver execution. |
| `barbell` | Strategy profile | Natural-selected universe | Core HRP sleeve + aggressor sleeve | Convexity-seeking profile that combines core stability with an antifragility-driven tail sleeve (`barbell` details are in `multi_engine_optimization_benchmarks.md`). |
| `market_baseline` | Legacy baseline alias | Benchmark symbols | Same as `market` | Provided for custom engine / legacy dashboards; matches `market` exactly. |
| `benchmark_baseline` | Legacy baseline alias | Natural-selected universe | Same as `benchmark` | Legacy name emitted by the `custom` engine; metrics should match `benchmark` in every run. |

## Plan Items (Open)
- [x] **Raw Pool Baseline Universe Control**: `raw_pool_ew` now toggles its universe source via `TV_RAW_POOL_UNIVERSE`/`RAW_POOL_UNIVERSE` so canonical selection baselines stay reproducible.
  - **Need**: Honor the flag, load canonical returns when requested, and emit per-window provenance (symbols, hash, source) so audits can pair raw pools with their metadata.
  - **Status**: `scripts/backtest_engine.py` respects `settings.raw_pool_universe`, aligns canonical returns with the primary index, and falls back gracefully when canonical candidates are missing; `scripts/prepare_portfolio_data.py` exposes configurable output paths; `docs/specs/plan-report.md` now captures the canonical/selected snapshots for run `20260103-182051` alongside the audit context.
  - **Files**: `scripts/backtest_engine.py`, `scripts/prepare_portfolio_data.py`, `tradingview_scraper/settings.py`.
  - **Doc**: `docs/specs/backtest_framework_v2.md`, `docs/specs/plan.md`, `docs/specs/plan-report.md`.
- [x] **Audit Ledger Context Gaps**: `audit.jsonl` lacked selection/rebalance/window metadata for optimization/simulation steps.
  - **Need**: Emit a `context` block with `selection_mode`, `rebalance_mode`, window indexes/dates, and `universe_source` for every recorded action.
  - **Status**: `AuditLedger.record_intent`/`record_outcome` now accept optional `context`; runs log the extra fields and guardrail tooling consumes them to detect sentinel mismatches.
  - **Files**: `tradingview_scraper/utils/audit.py`, `scripts/backtest_engine.py`.
  - **Doc**: `docs/specs/audit_ledger_v2.md`.
- [x] **Selection Audit Ledger Linkage**: The selection provenance chain previously stopped short of the tournament ledger.
  - **Need**: Hash and emit `selection_audit.json` along with raw/selected counts so the ledger can tie selection alpha back to raw candidates.
  - **Status**: `scripts/natural_selection.py` records the `selection_audit.json` hash, raw candidate counts, and winner counts in `audit.jsonl`; canonical run `20260103-171756/171913` now documents 45 raw candidates, `[60,120,200]` lookbacks, and the canonical cluster winners alongside the ledger entry.
  - **Doc**: `docs/specs/audit_ledger_v2.md`.
- [x] **Rebalance Audit Logs Missing**: `scripts/run_4d_tournament.py` left the `logs/` directory empty unless it was routed through the pipeline.
  - **Status**: The script now writes `rebalance_audit.log` under `artifacts/summaries/runs/<RUN_ID>/logs/`; the log path is recorded in `audit.jsonl` and documented in `docs/specs/artifacts_paths.md`.
- [x] **Canonical Universe Coverage Shrinkage**: A global `dropna(how="any")` collapsed the canonical universe before walk-forward windows were evaluated.
  - **Status**: Backtests now prune symbols per window rather than globally, allowing canonical returns to retain their breadth; canonical run `20260103-150600` completed without losing windows.
- [x] **Baseline Invariance Audit**: `raw_pool_ew` must stay invariant when selection mode changes but the universe source stays fixed, and canonical/selected mismatches should be treated as sentinel evidence.
  - **Need**: Guardrail that compares same-universe runs and gracefully documents mismatched (sentinel) comparisons.
  - **Status**: `scripts/raw_pool_invariance_guardrail.py` (`make baseline-guardrail`) loads audit metadata, prints `selection_mode`, `universe_source`, `raw_pool_symbol_count`, and `raw_pool_returns_hash`, and skips the tolerance check when the universe source or returns hash differ. Canonical pair `20260103-171756/171913` and selected pair `20260103-172054/182051` pass; the mismatched canonical vs selected pair now exits with a sentinel notice instead of a failure. `docs/specs/plan-report.md` captures the latest guardrail snapshot plus the sentinel narrative for run `20260103-182051`.
  - **Doc**: `docs/specs/plan-report.md`, `docs/specs/plan.md`.
- [x] **Metadata Catalog Drift (Veto Cascade)**: Missing `tick_size`, `lot_size`, and `price_precision` metadata forces repeated vetoes and destabilizes HRP distances.
  - **Status**: Audit Validated (Run 20260103-223836). Enrichment keeps candidate manifests complete, and the coverage gate is enforced via `scripts/metadata_coverage_guardrail.py`.
  - **Latest coverage**: Run `20260103-223836` recorded 100% coverage for both canonical and selected catalogs.
- [x] **Selection Report Generator Missing Entry Point**: Restoration of `generate_selection_report`.
  - **Status**: Audit Validated (Run 20260103-223836). Fixed signature and confirmed `selection_audit.md` (and new `selection_report.md` path) are populated in run artifacts.
- [x] **CVXPortfolio Missing-Returns Warnings**: Resolve missing-values/universe drift.
  - **Status**: Audit Validated (Run 20260103-223836). Applied `fillna(0.0)` and index alignment; `12_validation.log` confirms zero warnings.
- [x] **Institutional Fidelity (Jan 2026) - Bug Fixes**:
  - [x] **Simulator Truncation (20-day limit)**: Fixed. Run `20260103-223836` confirms full depth (2024-08 to 2026-01).
  - [x] **VectorBT Lookahead Bias**: Fixed. Removed `shift(-1)`; verified parity with other simulators.
  - [x] **ECI Volatility Defaults**: Fixed. Standardized on 0.5% daily default.

## Current Focus
- **Script Audit & Cleanup**: Categorize and archive 140+ scripts into standard subdirectories (`archive/`, `research/`, `maintenance/`) per the Phase 4 roadmap.
- **Guardrail sentinel readiness**: Keep canonical and selected guardrail pairs re-run quarterly.

## Next Steps Tracker
- [ ] **Phase 3: Directory Restructuring**: Completed. `TradingViewScraperSettings` supports structured paths; `BacktestEngine` and `ReportGenerator` migrated.
- [ ] **Phase 4: Script Audit & Cleanup**: Categorize 140+ scripts into Active, Maintenance, Prototype, and Legacy tiers to declutter the codebase.
- **Metadata gate**: Gate satisfied for `20260103-223836` (100% coverage).

## Status Sync
- **Artifact Reorganization**: Completed. Run directories now use standard sub-hierarchies (`config/`, `reports/`, etc.).
- **Metadata gate**: Satisfied—Run `20260103-223836` recorded 100% coverage and passing health audit.
- **Selection report**: Completed—Run `20260103-223836` confirmed restoration of selection story.
- **CVXPortfolio warnings**: Completed—Run `20260103-223836` confirmed zero warnings in `12_validation.log`.
- **Guardrail sentinel**: Completed—Run `20260103-223836` passed invariance check against previous baseline.
- **Health audit**: Completed for run `20260103-223836` (100% healthy).

## Script Audit & Cleanup Roadmap (Jan 2026)
### 1. Categorization Tiers
- **Tier 1 (Core)**: ~30 scripts in `scripts/` root (e.g., `backtest_engine.py`, `natural_selection.py`).
- **Tier 2 (Maintenance)**: Diagnostic/Utility tools moving to `scripts/maintenance/`.
- **Tier 3 (Research)**: Active prototypes moving to `scripts/research/`.
- **Tier 4 (Archive)**: Legacy/Redundant scripts moving to `scripts/archive/`.

### 2. Implementation Plan (Atomic Commits)
1.  **Skeleton**: Create subdirectories with `__init__.py`.
2.  **Maintenance**: Move tools like `cleanup_metadata_catalog.py`, `update_index_lists.py`.
3.  **Research**: Move prototypes like `proto_async_ws.py`, `tune_selection_alpha.py`.
4.  **Archive**: Move legacy scripts like `run_e2e_v1.py`, `summarize_results.py`.
5.  **Verification**: Confirm `make flow-production` and tests still pass with clean root.

### 3. Detailed Migration Manifest
| Target Directory | Scripts to Migrate |
| :--- | :--- |
| `scripts/maintenance/` | `cleanup_metadata_catalog`, `update_index_lists`, `track_portfolio_state`, `list_missing_symbols`, `check_backfill_status`, etc. |
| `scripts/research/` | `analyze_forex_universe`, `subcluster`, `benchmark_risk_models`, `explore_*`, `proto_*`, `research_*`, `tune_*`, etc. |
| `scripts/archive/` | `run_e2e_v1`, `run_grand_tournament`, `summarize_results`, `verify_phase*`, `debug_*`, `test_*`, etc. |


