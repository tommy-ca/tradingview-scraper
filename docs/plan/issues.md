# Project Implementation Roadmap: 2025 Standard

This document tracks the phased development of the TradingView Scraper institutional quantitative platform.

### Phase 1 through 8 (Finalized)
- Core Infrastructure, Metadata, Discovery, and Cascading Pruning.

### Phase 9 — Multi-Simulator Backtesting Framework (Finalized)
1. **Simulator Abstraction**: Refactor `BacktestEngine` to support modular simulation backends (`BaseSimulator`).
2. **Returns Simulator**: Move existing idealized dot-product logic to a formal `ReturnsSimulator`.
3. **CVXPortfolio Simulator**: Implement high-fidelity `CvxPortfolioSimulator` with transaction cost modeling (5bps slippage, 1bp commission).
4. **Lakehouse Bridge**: Implement `LakehouseDataInterface` to provide Prices/Returns/Volumes from Parquet to `cvxportfolio`.
5. **Alpha Decay Audit**: Update tournament reporting to compare Idealized vs. Realized Sharpe ratios.

### Phase 10 — 3D Tournament Matrix (Engine x Simulator x Profile) (Finalized)
1. **Test-Driven Schema**: Define 3D JSON schema in `tests/test_tournament_matrix.py`.
2. **Weight Caching**: Refactor `run_tournament` to optimize once per window and simulate multiple times.
3. **Multi-Simulator Support**: Accept a list of simulators in CLI and Makefile.
4. **Matrix Reporting**: Update `generate_backtest_report.py` to produce "Alpha Decay" audit tables.
5. **Full Validation**: Run production matrix and publish results to Gist.

### Phase 11 — Core Infrastructure Hardening & Performance (Finalized)
1. **Async Reliability**: Fix `AsyncScreener` retry logic by reraising aiohttp exceptions.
2. **Runtime Robustness**: Add guards for empty universes in `ClusteredOptimizerV2` and `natural_selection.py`.
3. **Clustering Logic**: Enable distance-based clustering thresholds in `natural_selection.py`.
4. **Scoring Consistency**: Centralize Liquidity/Alpha scoring math into a shared utility.
5. **Correlation Optimization**: Vectorize robust correlation calculation to handle large universes.
6. **Error Transparency**: Improve manifest parsing error feedback in `settings.py`.
7. **Solver Parity**: Upgrade standalone `scripts/optimize_clustered_v2.py` to `cvxpy` matching the modular engine.

### Phase 12 — Execution Fidelity & Optimizer Hardening (Finalized)
1. **Metric Unification**: Centralize Sharpe/MDD/CVaR calculations to a shared utility to remove simulator bias.
2. **Simulator Debugging**: Investigate "Execution Alpha" (Realized > Idealized) anomalies in `CvxPortfolioSimulator`.
3. **Engine Tuning**: Calibrate `cvxportfolio` and `riskfolio` default parameters for better production performance.
4. **Data Quality Gate**: Implement a mandatory health gate in `daily-run` that blocks optimization if data integrity is compromised.
5. **Integrated Self-Healing**: Automatically trigger `make recover` within the pipeline if gaps persist after alignment.

### Phase 13 — Visual Analytics & Tear-sheets (QuantStats) (Finalized)
1. **Integration**: Implement `scripts/generate_tearsheets.py` using `quantstats`.
2. **HTML Teardowns**: Produce full walk-forward tear-sheets for every engine/profile.
3. **Gist Enrichment**: Publish QuantStats metric snapshots to the implementation Gist.
4. **Benchmark Parity**: Ensure `SPY` benchmark data is correctly localized for all `quantstats` comparisons.
5. **Metric Unification**: Centralize Sharpe/Sortino/Calmar calculations in `utils/metrics.py` using QuantStats.
6. **Markdown Full Reports**: Implement `get_full_report_markdown` for high-density Gist artifacts.
7. **Golden Artifact Selection**: Implement intelligent Gist payload selection (32 essential files).

### Phase 14 — Institutional Reproducibility & Workflow Hardening (Finalized)
1. **Unified Configuration**: Align parameter names across JSON schema, Pydantic, and Shell.
2. **Global Manifest Export**: Ensure manifest variables are available to all Makefile targets.
3. **Provenance Archiving**: Automatically copy the active manifest into the run-scoped results directory.
4. **Zero-Tolerance Health Gate**: Enforce `strict_health` by default in the production profile.
5. **Tournament Source-of-Truth**: Refactor all reporting to derive baseline Strategy Resumes from the 3D Tournament matrix.

### Phase 15 — Secular Validation & Baseline Correction (Finalized)
1. **SPY Remediation**: Force overwrite `AMEX:SPY` with 500d high-integrity data to fix price drift.
2. **Lookback Extension**: Update production lookback to 500d to support a 200d total backtest window.
3. **Calendar Hardening**: Update returns matrix logic to correctly handle 24/7 Crypto vs 5/7 TradFi without zero-padding bias.
4. **Benchmarking Depth**: Ensure the 3D Tournament matrix covers the full 200d realized test target.
5. **Universal Baseline**: Centralize `baseline_symbol` in the manifest for consistent reporting.

### Phase 16 — Unified QuantStats Reporting & Standardized Baseline (Finalized)
1. **Market Engine**: Refactor SPY baseline as a first-class "Market" portfolio engine.
2. **Consolidated Reporting**: Implement `scripts/generate_reports.py` rebasing all summaries on QuantStats.
3. **Single Source of Truth**: Derive all high-level and detailed metrics from `tournament_results.json`.
4. **Markdown Native**: Standardize on high-density Markdown strategy teardowns for institutional visibility.
5. **Immutable Baseline**: Ensure the "Market" engine loads raw data directly, bypassing direction flipping.
6. **Detailed Analysis**: Added hierarchical and volatility cluster analysis reports integrated into the unified pipeline.

### Phase 17 — Hierarchical Risk Parity (HRP) Audit & Alignment (Finalized)
1. **Mathematical Audit**: Review and compare HRP objective functions across all 5 engines.
2. **Linkage Standardization**: Force all HRP backends to use Ward linkage.
3. **Numerical Stability**: Implement Epsilon Jitter to prevent empty-slice warnings in QuantStats.

### Phase 18 — VectorBT High-Performance Simulation
1. **Simulator Integration**: Implement `VectorBTSimulator` utilizing vectorized returns-based rebalancing.
2. **Standardized Metrics**: Force `vectorbt` results through the unified QuantStats metrics engine.
3. **Tournament Extension**: Expand the 3D matrix to support a 3-way simulation comparison (Idealized vs Convex vs Vectorized).
4. **Friction Calibration**: Map slippage and commissions to `vectorbt` fee structures.
