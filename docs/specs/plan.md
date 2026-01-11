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

### Phase 80: Base Universe Hardening & Normalization (COMPLETED)
- [x] **Specs**: Refined CR-151 to enforce three-stage "Prefetch -> Normalization -> Liquidity" filter.
- [x] **Audit**: Identified non-normalized fiat volume (IDR, TRY) as a primary discovery bottleneck.
- [x] **Config**: Updated `binance_perp_top100.yaml` and `binance_spot_top100.yaml` with explicit USD-stable match filters and 5000-deep prefilters.
- [x] **Lookback**: Aligned secular history and floor to 180 days (CR-103).
- [x] **Validation**: Reached the Top 50 target for Perps and 45 institutional anchors for Spot.

### Phase 81: High-Conviction Selection Hardening (COMPLETED)
- [x] **Logic**: Implemented Adaptive Friction Gate with 25% alpha-budget buffer.
- [x] **Config**: Set 0.50 threshold and -0.5 momentum floor for balanced alpha capture.
- [x] **Isolation**: Enforced 0.50 clustering distance to ensure factor orthogonality.
- [x] **Validation**: Verified 31 "Balanced Alpha" winners from 78 identities.

### Phase 82: Native Workflow & Temporal Alignment (COMPLETED)
- [x] **Infra**: Shifted to `uv run` native command flow for all pipeline stages.
- [x] **Data**: Verified `timestamp` indexing consistency across lakehouse parquet assets.
- [x] **Audit**: Confirmed 214 -> 108 -> 64 -> 31 funnel reduction using v3.2.3 standards.
- [x] **Specs**: Updated requirements to v3.2.3, locking native workflow and temporal standards.

### Phase 83: Metadata & Balanced Alpha Hardening (COMPLETED)
- [x] **Spec**: Added CR-155 (Mandatory Metadata) and updated CR-104/106 (Balanced Alpha standards).
- [x] **Infra**: Integrated `enrich_candidates_metadata.py` into core pipeline sequence.
- [x] **Logic**: Refined dynamic ECI hurdle for turnaround plays (momentum > -0.5).

### Phase 84: Persistence-Aware Risk Hardening (COMPLETED)
- [x] **Audit**: Identified 10 "Toxic Persistence" assets (persistent downtrends) dragging down portfolio performance.
- [x] **Logic**: Implemented CR-156 (Toxic Persistence Veto) in Selection Engine v3.2.5.
- [x] **Verification**: Verified removal of persistent drifters (BTC, XRP) from the qualified pool.

### Phase 85: Benchmark Stability & Rebalance Alignment (COMPLETED)
- [x] **Logic**: Implemented CR-157 (Benchmark Exemption) to allow SPY as a stability anchor.
- [x] **Config**: Standardized rebalance window to 5 days initially, then optimized to 20 days.
- [x] **Symmetry**: Integrated `binance_perp_secular_short` to profit from persistent downward drift.
- [x] **Audit**: Verified portfolio performance improvement with stabilized macro anchors and short alpha.
- [x] **Docs**: Updated Requirements and Design Docs to v3.2.7.

### Phase 86: Rebalance Optimization & Final Certification (COMPLETED)
- [x] **Audit**: Executed Rebalance Sensitivity Audit (v3.2.7) across [5, 10, 15, 20] day windows.
- [x] **Metric**: Identified 20-day window as Sharpe-optimal (2.36) for the current cross-asset regime.
- [x] **Funnel**: Validated 214 -> 108 -> 64 -> 35 refinement funnel metrics.
- [x] **Certification**: Locked v3.2.9 institutional standards for Q1 2026 Production.

### Phase 87: Forensic Hardening & Configuration Lock (COMPLETED)
- [x] **Fix**: Resolved "Inner Join Trap" in clustering engine via Pairwise Correlation.
- [x] **Logic**: Codified Toxic Persistence rationale and Benchmark Exemption (CR-156, CR-157).
- [x] **Infra**: Consolidated all forensic parameters (`min_col_frac`, `eci_hurdle`) into single-source manifest and Pydantic-settings.
- [x] **Docs**: Updated Requirements and Design specs to v3.2.9.
- [x] **Verification**: Verified 35-winner universe representation in final optimization.
