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
- **Primary Model (v3.2)**: Log-Multiplicative Probability Scoring (Log-MPS).
- **Secondary Model (v2.1)**: Additive Rank-Sum (CARS 2.1) for drawdown protection.
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

### 3.2 Refinement Funnel (5-Stage)
1. Discovery -> 2. Normalization -> 3. Metadata Enrichment -> 4. Identity Deduplication -> 5. Statistical Selection.

## 4. Development Plan (Current Sprint)

### Phase 100: TDD Hardening & Feature Flags (COMPLETED)
- [x] **TDD**: Implemented unit tests for Directional Purity and Dynamic Direction logic.
- [x] **Infra**: Gated experimental features behind feature flags in `TradingViewScraperSettings`.
- [x] **Audit**: Window-by-window forensic audit of risk profiles with deep ledger tracking.
- [x] **Analysis**: Comparative study of HRP failure modes (Crypto vs Institutional ETF).

### Phase 101: Synthetic Long Normalization & Logic Sync (COMPLETED)
- [x] **Logic**: Moved directional inversion to the data normalization layer prior to selection/allocation.
- [x] **Engine**: Audited `engines.py` to remove direction-aware code paths; models are now direction-naive.
- [x] **Backtest**: Verified simulators correctly reconstruct `Net_Weight` from normalized outputs.
- [x] **Docs**: Updated Requirements (v3.3.1) and Design Section 22.

### Phase 102: Deep Forensic reporting & Full Matrix Audit (COMPLETED)
- [x] **Report**: Developed `generate_deep_report.py` for human-readable window-by-window analysis.
- [x] **Hardening**: Increased Permutation Entropy resolution (Order=5, 120 permutations) to fix false-positive noise vetoes.
- [x] **Accuracy**: Fixed percentage scaling and restored missing risk metrics (Vol/DD) in tournament summaries.
- [x] **Robustness**: Implemented Annualized Return Clipping (-99.99%) to prevent mathematical anomalies in high-drawdown regimes.
- [x] **Traceability**: Enabled full return series persistence (`PERSIST_RETURNS=1`) for bit-perfect auditability.
- [x] **Verification**: Confirmed bit-perfect replayability of all portfolios from ledger context.

### Phase 103: System Sign-Off & Q1 2026 Freeze (COMPLETED)
- [x] **Release**: Created git tag `v3.3.1-certified`.
- [x] **Docs**: Final synchronization of Requirements, Design, and Agent Guide.
- [x] **Ledger**: Verified zero-error status across the final audit chain.
- [x] **Stability**: Hardened numerical pipelines (std/var) with `ddof=0` and explicit length guards. Suppressed residual 3rd-party RuntimeWarnings.
- [x] **Hardening**: Implemented Annualized Return Clipping (-99.99%) for extreme regimes.
- [x] **Protocol**: Implemented Selection Scarcity Protocol (SSP) for robust multi-stage fallbacks (Max-Sharpe -> Min-Var -> EW).

### Phase 104: Optimization Engine Refinement (COMPLETED)
- [x] **Riskfolio HRP**: Analyze divergence (-0.95 correlation). Result: **Deprecate for production**. Riskfolio engine now warns and falls back or is used only for research.
- [x] **PyPortfolioOpt**: Investigate `max_sharpe` warning with L2 regularization. Action: **Suppressed warning** in engine wrapper to maintain consistent API behavior while acknowledging solver limitations.
- [x] **Adaptive Logging**: Review `AdaptiveMetaEngine` logging verbosity. Action: **Reduced to DEBUG** level to eliminate log spam during backtests.
- [x] **Engine Consolidation**: Evaluate redundancy. Result: `skfolio` and `custom` are primary; `riskfolio` is secondary/experimental.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.3.1)

