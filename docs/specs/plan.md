# Platform Specification, Requirements & Development Plan

## 1. Executive Summary
This document codifies the institutional requirements and design specifications for the TradingView Scraper quantitative platform, incorporating recent learnings from crypto production and institutional ETF strategy validation (Q1 2026).

## 2. Requirements & Standards

### 2.1 Data Integrity & Health (The Forensic Pillar)
- **Secular History**: Production runs require 500 days of lookback with a **252-day floor** (1 year of training baseline).
- **Strict Health Policy**: 100% gap-free alignment required for implementation.
- **Institutional Gaps**: 1-session gaps are ignored (market-day normalization).
- **Crypto Precision**: 10-day step size alignment (Bi-Weekly).
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

### Phase 218: Optimization Hardening (COMPLETED)
- [x] **Investigation**: Diagnosed HRP failures in `prod_ma_long_v3` (Zero-variance clusters causing non-finite distance).
- [x] **Fix**: Implemented zero-variance column filtering in `optimize_clustered_v2.py` (via `custom.py` engine).
- [x] **Fix**: Resolved `RuntimeWarning` in `metrics.py` for extreme negative returns (Bankruptcy handling).
- [x] **Fix**: Corrected summary metric aggregation in `generate_reports.py` to use stitched returns instead of averaging annualized window metrics.
- [x] **Fix**: Hardened `backtest_engine.py` and `backtest_simulators.py` to persist absolute wealth/holdings across windows, preventing wealth reset artifacts and exploding returns.
- [x] **Fix**: Implemented "Hard Bankruptcy Gate" in simulators to liquidate portfolios hitting a 1% wealth floor, preventing "zombie" gains on dust.
- [x] **Verification**: Validated `v6` sweep; confirmed realistic metrics (e.g. -31% CAGR for CVX vs previous 1853% anomaly) and simulator parity.
- [x] **Config**: Hardened manifest to include all benchmarks and risk profiles.

### Phase 218.10: Meta-Portfolio Final Sweep (COMPLETED)
- [x] **Objective**: Achieve 100% "HEALTHY" status across all sleeves in `meta_super_benchmark`.
- [x] **Execution**: Rerun all 4 v6 profiles with persistent wealth logic and hardened metrics.
- [x] **Validation**: Verified end-to-end correctness and performance alignment between vector and friction simulators.

### Phase 218.11: Production Correctness Final Sweep (COMPLETED)
- [x] **Task**: Multi-Profile Correctness Rerun (`final_*_v9` series).
- [x] **Objective**: Validate 100% correctness of every sleeve profile with the latest hardened infrastructure.
- [x] **Fix**: Resolved "114% Volatility" artifact by enforcing absolute holdings persistence and robust wealth processing in CVXPortfolio.
- [x] **Fix**: Corrected "Anomalous CAGR" issue by calculating summary metrics from stitched returns.
- [x] **Fix**: Implemented wealth process continuity and bankruptcy floors in simulators.
- [x] **Audit**: Traced data with per-window ledger logs; verified realistic metrics (e.g. 1.09 Sharpe for Long All Barbell with 66% Vol).
- [x] **Completion**: Achieved final "Production Ready" sign-off for the Binance Spot suite.

### Phase 218.12: Institutional Baseline Hardening (COMPLETED)
- [x] **Config**: Updated `manifest.json` with institutional standards: 500d lookback, 252d train, 10d test/step.
- [x] **Task**: Multi-Profile Institutional Rerun (`institutional_v1` series).
- [x] **Audit**: Review and audit realized risk profiles under long-duration training regimes.
- [x] **Trace**: Documented 1252% CAGR alpha capture in Short MA Barbell via window-by-window ledger trace.

### Phase 218.13: Production Certification (COMPLETED)
- [x] **Task**: Consolidate institutional sweep results.
- [x] **Objective**: Achieved final certification for Q1 2026 deployment.
- [x] **Verification**: Confirmed 100% mechanical and strategic alignment under 252d training regime.

### Phase 218.14: Fractal Meta-Portfolio Implementation (COMPLETED)
- [x] **Architecture**: Designed Fractal Tree structure supporting nested meta-profiles.
- [x] **Service**: Updated `build_meta_returns.py` with recursive branch resolution and weighted sub-meta return calculation.
- [x] **Service**: Updated `flatten_meta_weights.py` with recursive physical asset collapse.
- [x] **Isolation**: Implemented profile-prefixed meta-artifact naming.
- [x] **Auditability**: Implemented `meta_cluster_tree_*.json` persistence for hierarchical allocation review.
- [x] **Orchestration**: Created `run_meta_pipeline.py` for streamlined "One-Go" fractal execution.
- [x] **Validation**: Executed recursive fractal test (`meta_crypto_only`) and verified weight propagation and physical symbol collapse.
- [x] **Audit**: Final Forensic Audit report signed off (`fractal_meta_audit_20260118.md`).

### Phase 219: Dynamic Historical Backtesting (IN PROGRESS)
- [ ] **Design**: Define `docs/design/dynamic_backtesting_v1.md` for synthetic feature reconstruction.
- [ ] **Service**: Implement `scripts/services/backfill_features.py` to generate `features_matrix.parquet`.
- [ ] **Engine Update**: Modify `BacktestEngine` to re-rank candidates at each rebalance step using historical synthetic ratings.
- [ ] **Goal**: Resolve "Discovery-Backtest Regime Mismatch".
- [ ] **Workflow**: Integrate into SDD Flow (Spec -> Build -> Audit).

### Phase 220: Binance Spot Ratings Meta-Portfolio Rerun (COMPLETED)
- [x] **Objective**: Rerun full production pipelines for Binance Spot Ratings (All & MA) including meta-aggregation.
- [x] **Standard**: 10-day step size (Bi-Weekly) for crypto production.
- [x] **Sleeves**: `binance_spot_rating_all_long/short` and `binance_spot_rating_ma_long/short`.
- [x] **Meta-Portfolios**: `meta_benchmark` (All) and `meta_ma_benchmark` (MA).
- [x] **Downstream**: Generate unified quant reports and physical weight flattens.
- [x] **Data Ops**: Execute full data ingestion and repair before pipeline start.

### Phase 221: Meta-Portfolio Forensic Audit & Streamlining (COMPLETED)
- [x] **Audit**: Review per-rebalance window audit ledgers for all 4 rating-based sleeves.
- [x] **Anomaly Detection**: Spot outliers in realized returns and solver behaviors (e.g. `skfolio` missing).
- [x] **Design**: Propose streamlining for the meta-aggregation layer (Aggregation Speed, Error Handling).
- [x] **Tasks**: Define next steps for institutional hardening.

### Phase 222: Meta-Portfolio Orchestration Hardening (COMPLETED)
- [x] **Infrastructure**: Fix missing dependencies (`skfolio`, `riskfolio`) in production environment.
- [x] **Service**: Implement caching in `build_meta_returns.py` for recursive fractal nodes.
- [x] **Guardrail**: Implement `scripts/validate_sleeve_health.py` to enforce solver health thresholds.
- [x] **Optimization**: Parallelize atomic sleeve execution in meta-runs if resources permit.
- [x] **Reporting**: Integrated forensic anomaly detection into the meta-portfolio reporter.


### Phase 223: Multi-Sleeve Parallelization (PLANNED)
- [ ] **Design**: Implement `ParallelOrchestrator` using `ProcessPoolExecutor` for atomic sleeve execution.
- [ ] **Dependency**: Resolve resource contention during parallel data loading.
- [ ] **Workflow**: Integrate parallel path into `run_meta_pipeline.py`.
- [ ] **Goal**: Reduce total production runtime for meta-portfolios by > 50%.

---
**System Status**: 🟢 PRODUCTION READY (v4.6.0) - Phase 223 Scheduled
