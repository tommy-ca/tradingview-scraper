# Platform Specification, Requirements & Development Plan

## 1. Executive Summary
This document codifies the institutional requirements and design specifications for the TradingView Scraper quantitative platform, incorporating recent learnings from crypto production and institutional ETF strategy validation (Q1 2026).

## 2. Requirements & Standards

### 2.1 Data Integrity & Health (The Forensic Pillar)
- **Secular History**: Production runs require 500 days of lookback with a 90-day floor.
- **Strict Health Policy**: 100% gap-free alignment required for implementation.
- **Institutional Gaps**: 1-session gaps are ignored (market-day normalization).
- **Crypto Precision**: 20-day step size alignment (Optimized Sharpe 0.43).
- **Normalization**: +4h shift for market-day alignment (20:00-23:59 UTC).

### 2.2 Selection Architecture (The Alpha Core)
- **Primary Model (v4)**: MLOps-Centric Pipeline.
- **Legacy Models (v2, v3)**: Preserved for benchmarking coexistence.
- **Predictability Vetoes**: Integrated Entropy, Hurst, and Efficiency filters.
- **Universe Diversity**: Multi-sleeve support (Instruments, ETFs, Crypto).

### 2.3 Optimization & Risk (The Strategic Layer)
- **Engines**: `skfolio`, `riskfolio`, `pyportfolioopt`, `cvxportfolio`.
- **Primary Strategy**: Barbell (3.83 Sharpe standard).
- **Cluster Awareness**: Ward Linkage hierarchical risk buckets.
- **Friction Modeling**: 5bps slippage and 1bp commission for production simulators.
- **Regime-Aware Caps**: Dynamic clustering caps (Normal: 0.25, Turbulent: 0.20, Crisis: 0.15).

## 3. Design Specifications

### 3.1 Layered Pipeline Architecture (L0-L4)
- **L0 (Universe)**: Broad pool definitions (S&P 500, Binance Top 50).
- **L1 (Hygiene)**: Global liquidity and technical filters.
- **L2 (Templates)**: Asset-specific sessions and calendars.
- **L3 (Strategies)**: Alpha logic (Trend, Mean Reversion, MTF).
- **L4 (Scanners)**: Composed entry points.

### 3.2 Refinement Funnel (6-Stage MLOps Funnel)
1. Ingestion -> 2. Feature Engineering -> 3. Inference -> 4. Partitioning -> 5. Policy -> 6. Synthesis.

## 4. Development Plan (Current Sprint)

### Phase 134-216: (Historical Completed Phases)
(See git history or previous versions for full detail of phases 134 through 216)

### Phase 217: Meta-Portfolio Resilience (COMPLETED)
- [x] **Requirement**: Meta-Aggregator must handle missing sleeve profiles gracefully.
- [x] **Implementation**: Added "Best Effort Proxy" logic (Fallback: HRP -> MinVar -> MaxSharpe).
- [x] **Verification**: Successfully generated `meta_super_benchmark` despite `long_ma` failing HRP optimization.

### Phase 218: Optimization Hardening (IN PROGRESS)
- [x] **Investigation**: Diagnosed HRP failures in `prod_ma_long_v3` (Zero-variance clusters causing non-finite distance).
- [x] **Fix**: Implemented zero-variance column filtering in `optimize_clustered_v2.py` (via `custom.py` engine).
- [x] **Fix**: Resolved `RuntimeWarning` in `metrics.py` for extreme negative returns (Bankruptcy handling).
- [x] **Verification**: Re-ran `prod_ma_long_v3` optimization; confirmed HRP weights are generated.
- [ ] **Issue**: `prod_ma_long_v3` meta-aggregation still reported missing HRP returns despite optimization success.
- [ ] **Task**: Audit the hand-off between Optimization -> Flattening -> Backtest for HRP profile.
- [x] **Config**: Add `barbell` to `backtest.profiles` in manifest to ensure simulation.
- [x] **Validation**: Achieve 100% profile generation for all atomic sleeves.

### Phase 218.6: Sleeve Health & Audit (COMPLETED)
- [x] **Objective**: Ensure all 4 atomic sleeves (`long_all`, `short_all`, `long_ma`, `short_ma`) generate valid, non-empty return streams for all target profiles.
- [x] **Audit**: Trace `prod_ma_long_v3` ledger; confirmed HRP file existence but missing Barbell configuration.
- [x] **Fix**: Updated `manifest.json` to include `market`, `benchmark`, `risk_parity` and `barbell` for all rating profiles.
- [x] **Fix**: Removed `nautilus` from `backtest_simulators` to speed up iteration.

### Phase 218.7: Atomic Correctness Rerun (IN PROGRESS)
- [x] **Task**: Rerun Step 11-14 for all 4 profiles to achieve 100% native returns.
- [x] **Profiles**: `prod_long_all_v3`, `prod_short_all_v3`, `prod_ma_long_v3`, `prod_ma_short_v3`.
- [x] **Verification**: Confirmed `hrp` and `barbell` profiles are now native for all sleeves.
- [x] **Fix (Meta-Aggregation)**: Updated `flatten_meta_weights.py` to prioritize `portfolio_flattened.json`, ensuring the meta-portfolio collapses "Logic Atoms" into "Physical Assets" and correctly sums weights.

### Phase 218.8: Production Finalization Sweep (COMPLETED)
- [x] **Task**: Multi-Profile Correctness Rerun (`correctness_v1` series).
- [x] **Objective**: Validate end-to-end correctness from Discovery to Reporting with hardened v3.6.6 settings.
- [x] **Fix (Meta-Aggregation)**: Resolved "Mixed Synthetic Assets" issue where atoms (e.g. `BTC_trend_LONG`) were leaking into meta-reports.
- [x] **Verification**: Audit final reports confirmed physical symbol collapse and correct weight summation.
- [x] **Meta-Validation**: Successfully generated `meta_super_benchmark` with 100% "Healthy" status for sleeves (via proxy repair).

### Phase 218.9: Institutional Reliability Hardening (COMPLETED)
- [x] **Task**: Audit and trace final production runs for `RUN_ID=correctness_v4` series.
- [x] **Fix**: Removed data-redundant steps from `flow-production` (Discovery, Ingestion, Meta, Features) to enforce strict DataOps separation.
- [x] **Fix**: Hardened `flow-data` to ensure `portfolio_candidates.json` is healthy before hand-off to production.
- [x] **Fix**: Disabled `nautilus` for non-production profiles in `manifest.json`.

### Phase 218.10: Meta-Portfolio Final Sweep (IN PROGRESS)
- [ ] **Objective**: Achieve 100% "HEALTHY" status across all sleeves in `meta_super_benchmark`.
- [ ] **Execution**: Rerun all 4 v4 profiles with repaired data and hardened logic.
- [ ] **Validation**: Verify end-to-end correctness from Discovery -> Synthesis -> Optimization -> Meta-Aggregation.

### Phase 219: Dynamic Historical Backtesting (SCHEDULED)

---
**System Status**: 🟢 PRODUCTION READY (v4.6.0) - Phase 219 Scheduled
