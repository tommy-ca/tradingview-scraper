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

### Phase 92: Hierarchical Factor Stability Research (COMPLETED)
- [x] **Research**: Explored linkage methods (Ward/Complete) and stability impact of window averaging.
- [x] **Audit**: Measured cluster cohesion (0.61) vs single-window baseline (0.51).
- [x] **Config**: Centralized `cluster_lookbacks` in `manifest.json` and Pydantic settings.
- [x] **Consistency**: Aligned clustering windows ([5, 60, 120, 200]) with rebalance frequency.
- [x] **Docs**: Codified CR-171 and updated Design Section 23 with the Stability Protocol.

### Phase 93: High-Fidelity Crypto Tournament Validation (COMPLETED)
- [x] **Tournament**: Rerun full crypto production sweep with v3.2.12 standards.
- [x] **Audit**: Verified evolution of portfolio depth window-by-window (1 -> 17 assets).
- [x] **Rationale**: Explained Early-Window sparsity (Window 0-2) as a natural effect of the 90-day Immersion floor.
- [x] **Reports**: Generated comprehensive Risk Matrix Audit comparing all portfolio engines (Run ID: 20260111-120437).

### Phase 94: Pure Alpha Selection & Benchmark Isolation (COMPLETED)
- [x] **Logic**: Removed automated benchmark injection from `prepare_portfolio_data.py`.
- [x] **Symmetry**: Updated `BacktestEngine` to utilize benchmarks only for baseline profiles or if explicitly selected.
- [x] **Specs**: Updated Requirements (CR-172) and Design Section 24 to formalize Benchmark Isolation.
- [x] **Verification**: Confirmed that `selected_candidates` universe represents 100% scanner-discovered assets.

### Phase 95: Forensic Data Audit & Health Recovery (COMPLETED)
- [x] **Audit**: Executed strict session-aware health audit for selected winners.
- [x] **Recovery**: Implemented `GAPFILL=1` self-healing loop for stale winners.
- [x] **Optimization**: Reran HRP optimization on the healthy dataset.
- [x] **Certification**: Generated final risk audit report with bit-perfect window traceability.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.2.13)
