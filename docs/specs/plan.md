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

### Phase 134: Champion/Challenger Production Rollout (COMPLETED)
- [x] **Dual-Run Config**: Updated `run_master_tournament.py` to include `v4` in the selection lineup.
- [x] **Adapter Layer**: Created `SelectionPipelineAdapter` to bridge `SelectionContext` to `SelectionResponse`.
- [x] **Shadow Mode**: Enabled `v4` shadow execution in production tournaments.

### Phase 135: Deep Audit Integration & Telemetry (COMPLETED)
- [x] **Requirement**: Formalized CR-420 for granular telemetry segregation.
- [x] **Orchestrator Update**: Refactored `backtest_engine.py` to move audit trails to the `data` blob.
- [x] **Integration Test**: Verified end-to-end telemetry flow via `tests/test_audit_v4_integration.py`.

### Phase 136: Grand Tournament Validation (COMPLETED)
- [x] **Master Tournament Execution**: Executed head-to-head tournament (`v3.4` vs `v4`) across the risk matrix.
- [x] **Forensic Report Generation**: Created `Deep Forensic Reports` highlighting v4 MLOps telemetry.

### Phase 137: Selection Coexistence Standard (COMPLETED)
- [x] **Requirements Update**: Codified the "Multi-Version Coexistence" standard; retained v2, v3, and legacy engines.
- [x] **Full Production Tournament**: Executed exhaustive `crypto_production` matrix (Selection x Engine x Profile x Simulator).
- [x] **Cross-Version Benchmark**: Generated performance matrix confirming v4 dominance and v3 stability.

### Phase 138: Full Risk Matrix Audit (COMPLETED)
- [x] **Exhaustive Sweep**: Executed tournament with ALL risk profiles (`equal_weight`, `min_variance`, `risk_parity`, `max_sharpe`, `hrp`, `barbell`, `market_neutral`).
- [x] **Short Handling Audit**: Verified correct sign preservation in `Net_Weight` (-0.012 for SHORTs) and correct simulator mapping.
- [x] **HTR Loop Fix**: Patched `SelectionPipelineAdapter` to allow internal HTR looping (Stages 1-4).
- [x] **Data Hygiene Audit**: Identified and resolved "Sparse Parquet" bottleneck by prioritizing `portfolio_returns.pkl`.
- [x] **Performance Matrix**: Validated v4 dominance (Sharpe 4.05 vs v3.4 3.62 in MaxSharpe).

### Phase 139: Production Cutover & Documentation (PLANNED)
- [ ] **Default Engine Switch**: Update `BacktestEngine` and `ProductionPipeline` to default to `selection_mode="v4"`.
- [ ] **Legacy Archiving**: Move `v2` and `v3` implementation files to `legacy/` directory.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.4.8) - Alpha Matrix Validated
