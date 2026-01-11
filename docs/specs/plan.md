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

### Phase 98: Zero-Warning & Data Health Finalization (COMPLETED)
- [x] **Data**: Perform final `GAPFILL=1` recovery for any lingering stale assets.
- [x] **Logs**: Verify production execution is 100% free of `RuntimeWarning` and `UserWarning`.
- [x] **Tournament**: Execute final pre-live tournament to confirm "Clean Boot" state.

### Phase 99: Directional Purity & Allocation Alignment (COMPLETED)
- [x] **Spec**: Codified CR-181 (Directional Return Alignment) and CR-182 (Dynamic Direction).
- [x] **Rationale**: Formalized late-binding trend filter strategy in Design Section 22.1.
- [x] **Logic**: Implemented synthetic return inversion in `BacktestEngine`.
- [x] **Audit**: Verified HRP profit capture from persistent downtrends (Shorts) in forensic logs.
- [x] **Report**: Final system certification with balanced long/short contribution analysis.

### Phase 100: TDD Hardening & Feature Flags (COMPLETED)
- [x] **TDD**: Implemented unit tests for Directional Purity and Dynamic Direction logic.
- [x] **Infra**: Gated experimental features behind feature flags in `TradingViewScraperSettings`.
- [x] **Audit**: Window-by-window forensic audit of risk profiles with deep ledger tracking.
- [x] **Analysis**: Comparative study of HRP failure modes (Crypto vs Institutional ETF).

### Phase 101: Synthetic Long Normalization (IN_PROGRESS)
- [ ] **Logic**: Move directional inversion to the data normalization layer prior to selection/allocation.
- [ ] **Engine**: Audit portfolio engines to ensure they are direction-blind and operate purely on synthetic alpha.
- [ ] **Backtest**: Verify that simulators correctly reconstruct `Net_Weight` from normalized outputs.
- [ ] **Docs**: Updated Requirements (CR-181-184) and Design Section 22 to formalize the standard.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.2.16)
