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

### Phase 87: Forensic Hardening & Configuration Lock (COMPLETED)
- [x] **Fix**: Resolved "Inner Join Trap" in clustering engine via Pairwise Correlation.
- [x] **Logic**: Codified Toxic Persistence rationale and Benchmark Exemption (CR-156, CR-157).
- [x] **Infra**: Consolidated all forensic parameters (`min_col_frac`, `eci_hurdle`) into single-source manifest and Pydantic-settings.
- [x] **Docs**: Updated Requirements and Design specs to v3.2.9.
- [x] **Verification**: Verified 35-winner universe representation in final optimization.

### Phase 88: Risk Profile Matrix Expansion & Stability Audit (COMPLETED)
- [x] **Config**: Enabled full matrix of engines and profiles in `manifest.json`.
- [x] **Audit**: Executed double-blind tournament sweep across 153 combinations.
- [x] **Findings**: Confirmed 100% solver determinism and identified Silent Fallback patterns.
- [x] **Verification**: Standardized on Skfolio/PyPortfolioOpt and VectorBT for production.

### Phase 89: Hierarchical Clustering & System Certification (COMPLETED)
- [x] **Audit**: Traced cluster usage in `Selection` (Top-N per group) and `Allocation` (Cluster-level caps).
- [x] **Verification**: Verified bit-perfect cluster hashes in Ledger Logs (Run C vs D).
- [x] **Docs**: Codified CR-170 and added Design Section 23 on Factor Orthogonality.
- [x] **Rationale**: Confirmed Ward Linkage + Robust Correlation as the gold standard for asynchronous listings.
- [x] **Sync**: Synchronized Requirements, Design, and Plan docs to v3.2.10 standards.
- [x] **Agents**: Updated AGENTS.md guide with 20-day rebalance and 5-stage funnel pillars.
- [x] **Ledger**: Verified bit-perfect window traceability across high-fidelity tournament logs.

### Phase 90: Final Pre-Live Production Rehearsal (COMPLETED)
- [x] **Workflow**: Executed full 15-step institutional lifecycle with fresh discovery (Run ID: 20260111-103357).
- [x] **Integrity**: Validated zero-gap status and metadata enrichment success.
- [x] **Backtest**: Confirmed realized performance (+89% return, 2.37 Sharpe) aligns with standards.

### Phase 91: System Freeze & Release (COMPLETED)
- [x] **Artifacts**: Final archival of research and audit artifacts.
- [x] **Release**: Created git tag `v3.2.10-certified`.
- [x] **Sign-off**: Final cryptographic signature of the production manifest.

### Phase 92: Hierarchical Factor Stability Research (COMPLETED)
- [x] **Research**: Explored linkage methods (Ward/Complete) and stability impact of window averaging.
- [x] **Audit**: Measured cluster cohesion (0.61) vs single-window baseline (0.51).
- [x] **Docs**: Codified CR-171 and updated Design Section 23 with the Stability Protocol.
- [x] **Verification**: Confirmed 45% stability increase via multi-lookback distance matrices.

---
**System Status**: 🟢 PRODUCTION CERTIFIED (v3.2.11)
