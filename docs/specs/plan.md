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
- [x] **Benchmarking Standardization**: Quantified and standardized evaluation gates in `docs/specs/benchmark_standards_v1.md`.
  - **Robustness & Antifragility**: Temporal Fragility / Friction Alignment / Selection Stability / Quantified Antifragility are implemented in `tradingview_scraper/utils/metrics.py` and `scripts/research/audit_tournament_forensics.py`.
  - **Institutional Safety (Spec + Tooling)**: Added standards for Market Sensitivity (Beta), Concentration (HHI/Cluster Cap), Tail Risk (CVaR/MDD), Turnover Efficiency, Simulator Parity, and Regime Robustness; scoreboard + candidate filter is implemented in `scripts/research/tournament_scoreboard.py`.
  - **Scoreboard Learnings**: Recent tournament runs validated other gates but predate antifragility summary fields; strict scoreboard runs show missing `af_dist` / `stress_alpha` until a fresh tournament is re-run with the updated benchmark instrumentation.

## Current Focus
- **MLOps Scalability Pivot (Phase 6)**: Transition to Ray (Compute) and Prefect (Orchestration) to eliminate execution bottlenecks and focus on Alpha Core per `docs/specs/mlops_scalability_v1.md`.
- **Robustness Evaluation**: Benchmark 4D tournament results against **Temporal Fragility**, **Friction Alignment**, **Selection Stability**, and **Quantified Antifragility** (distribution + stress-response) to identify robust production candidates.
- **Guardrail sentinel readiness**: Keep canonical and selected guardrail pairs re-run quarterly.

## Next Steps Tracker
- [ ] **Phase 6: MLOps Integration**: Refactor backtest units into atomized tasks; integrate Ray shared object store.
- [ ] **Phase 5: Performance Optimization**: Implement multiprocessing/Ray logic in `Grand4DTournament`.
- [x] **Benchmark Gate: Quantified Antifragility**: Added strategy-level convexity and crisis-response metrics to tournament summaries (`scripts/backtest_engine.py`) and audits (`scripts/research/audit_tournament_forensics.py`).
- [x] **Benchmark Scoreboard Expansion**: Implemented `scripts/research/tournament_scoreboard.py` to generate a single tournament scoreboard + candidate filter (CSV + Markdown).
- [x] **Benchmark Scoreboard Validation Run**: Audit Validated (Run `20260104-163801`).
  - `TV_FEATURES__FEAT_AUDIT_LEDGER=1 TV_RUN_ID=20260104-163801 uv run scripts/research/grand_4d_tournament.py --selection-modes v3.2 --rebalance-modes window --engines skfolio --profiles barbell,hrp --simulators custom,cvxportfolio,nautilus`
  - `uv run scripts/research/tournament_scoreboard.py --run-id 20260104-163801`
  - `uv run scripts/archive/verify_ledger.py artifacts/summaries/runs/20260104-163801/audit.jsonl`
  - Barbell optimize outcomes recorded (5 success / 5 empty / 1 error; 0 missing intent→outcome gaps).
- [ ] **Full Grand 4D Sweep (Scoreboard-Ready)**: Run the default 4D grid with audit ledger enabled and per-cell returns persisted under `data/grand_4d/<rebalance>/<selection>/returns/`, then run the scoreboard strict.
  - `TV_FEATURES__FEAT_AUDIT_LEDGER=1 TV_RUN_ID=<RUN_ID> uv run scripts/research/grand_4d_tournament.py`
  - `uv run scripts/research/tournament_scoreboard.py --run-id <RUN_ID>`
- [x] **Grand 4D Orchestrator Parity**: Updated `scripts/research/grand_4d_tournament.py` to persist per-cell artifacts under `data/grand_4d/<rebalance>/<selection>/` (writes `tournament_results.json` + `returns/*.pkl` via the shared writer in `scripts/backtest_engine.py`).
- [x] **Audit Ledger Completeness Gate**: Updated `scripts/backtest_engine.py` to record `backtest_optimize` outcomes for success/empty/error and to record `backtest_simulate` errors as outcomes (eliminates silent intent→no-outcome gaps).
- [x] **Phase 3: Directory Restructuring**: Audit Validated (Run `20260103-235511`).

- [x] **Phase 4: Script Audit & Cleanup**: Completed. Categorized and archived 110+ scripts.
- **Metadata gate**: Gate satisfied for `20260103-235511` (100% coverage).

## Status Sync
- **Artifact Reorganization**: Audit Validated (Run `20260103-235511`).
- **Grand 4D Smoke Validation**: Audit Validated (Run `20260104-161534`). Verified per-cell persistence under `data/grand_4d/<rebalance>/<selection>/` and `backtest_summary` outcomes in `audit.jsonl`.
- **Benchmark Scoreboard Validation**: Audit Validated (Run `20260104-163801`). Verified per-cell `data/grand_4d/window/v3.2/returns/*.pkl`, ledger integrity, and strict scoreboard generation (no silent `backtest_optimize` gaps; barbell empty/error outcomes are recorded).
- **Scoreboard Generation (uv minimal env)**: Validated (Run `20260104-165334`). `uv run scripts/research/tournament_scoreboard.py --run-id latest --allow-missing` generates `data/tournament_scoreboard.csv`, `data/tournament_candidates.csv`, and `reports/research/tournament_scoreboard.md` without requiring `tabulate` (markdown fallback).
- **4D Tournament Validation**: Audit Validated (Run `20260104-005636`). Completed full multi-dimensional sweep (Selection x Rebalance x Simulator x Engine). `v3.2 / skfolio / barbell` established as the champion configuration with Sharpe 3.96. High-fidelity parity confirmed between `nautilus` and `cvxportfolio`.
  - **Scoreboard note**: This run does not include `data/returns/*.pkl` and contains no `backtest_summary` events in `audit.jsonl`, so strict candidates fail on missing `af_dist` / `stress_alpha`.
  - **Audit ledger deep check**: Hash chain verified; `backtest_simulate` successes = 13,992; `backtest_optimize` intents = 3,465 vs successes = 3,201 (264 missing, mostly barbell), which also reduces window coverage for some configs.
  - **Fix implemented**: Grand 4D sweeps now persist per-cell `returns/*.pkl` and backtest engine records optimize outcomes; rerun required to validate strict candidates.
  - **Scoreboard validation**: Scoreboard generation succeeds on the latest run that includes `data/tournament_results.json` + `data/returns/*.pkl` (e.g., `20260104-003407`), but strict candidates remain empty until antifragility is present in tournament summaries.
- **Metadata gate**: Satisfied—Run `20260104-005636` recorded 100% coverage.
- **Selection report**: Completed—Confirmed restoration of selection story in run artifacts.
- **CVXPortfolio warnings**: Resolved—Run `20260104-005636` confirms zero "universe mismatch" warnings in tournament logs.
- **Guardrail sentinel**: Completed—Passed invariance check against previous baseline.
- **Health audit**: Completed for latest production run (100% healthy).
- **Dev env (uv)**: Synced with `uv sync --all-extras`; validated `uv run pytest`.
- **Streamer end-of-history exit**: `Streamer.stream()` only starts idle packet counting after the first OHLC/indicator payload; requesting beyond available history returns partial OHLC quickly.
  - [x] **Spec**: Updated WebSocket guardrails in `docs/specs/data_resilience_v2.md`.
  - [x] **Spec**: Updated handshake-safe idle guidance in `docs/specs/price_stream_resilience.md`.
  - [x] **Audit**: `uv run pytest -q tests/test_streamer_parity.py::TestStreamerParity::test_graceful_timeout_handling`.
- **Risk profile spec audit**: Synced barbell/HRP/market/max_sharpe specs to production.
  - Barbell aggressors: top clusters (1 leader/cluster), default schedule QUIET 15% / NORMAL 10% / TURBULENT 8% / CRISIS 5%.
  - Market tag: `Cluster_ID: MARKET`.
  - Max Sharpe ridge: configurable via `EngineRequest.l2_gamma` (default 0.05).
  - **Validation**: `uv run pytest -q tests/test_portfolio_engines.py` and `uv run pytest`.
  - **Pytest warnings**: Resolved (0 warnings) after:
    - Replaced `pkg_resources` resource loading with `importlib.resources` in the `technicals` and `news` scrapers.
    - Cast `timezone` / `session` to string in `cleanup_metadata_catalog.py` before patching crypto defaults.
    - Avoided `pd.concat` against empty/all-NA frames in `MetadataCatalog` upserts/retirements.
    - Computed Calmar without triggering QuantStats divide-by-zero behavior.
    - Suppressed numpy runtime warnings inside the ADF stationarity score call.


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
