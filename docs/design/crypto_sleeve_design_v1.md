# Crypto Sleeve Design Document v3.2.8

## 1. Architecture Overview

### 1.1 System Context
The crypto sleeve operates as an independent capital allocation unit within the Fractal Risk Meta-Portfolio architecture, providing orthogonal exposure to digital assets while maintaining institutional-grade risk controls.

### 1.2 Design Principles
1. **BINANCE-Only Focus**: Highest liquidity, cleanest execution.
2. **Short-Cycle Momentum**: Daily/Weekly/Monthly (no 3M/6M anchors).
3. **Noise Floor Selection**: Filter white noise, delegate weighting to risk engines.
4. **Calendar Integrity**: 24x7 XCRY calendar with inner join for meta-portfolio.
5. **Barbell Risk**: Safe Haven anchors (90%) + Aggressors (10%).
6. **HRP Dominance**: Hierarchical Risk Parity as the primary stability profile.
7. **Temporal Alignment**: Rebalancing windows optimized via persistence analysis.
8. **Forensic Integrity**: 20-day rebalancing cycle as the current regime standard, providing optimal risk-adjusted alpha (Sharpe 0.43) for cross-asset portfolios.

---

## 21. Refinement Funnel Architecture

### 21.1 Liquidity Normalization & The Discovery Funnel
A forensic audit of global crypto liquidity reveals that raw screener metrics (`Value.Traded`) are not USD-normalized across currency pairs. Local fiat pairs (IDR, TRY, ARS) can dominate the rank with local-currency denominated volume.

To ensure institutional signal quality, the Discovery Layer implements a **Five-Stage Refinement Funnel**:
1.  **Stage 1 (Discovery)**: Fetches up to 5000 candidates sorted by raw liquidity from verified CEXs. (Result: ~214 symbols).
2.  **Stage 2 (USD-Normalization)**: Explicitly filters for institutional quote patterns (`USDT`, `USDC`, `FDUSD`) at the source. (Result: ~108 symbols).
3.  **Stage 3 (Metadata Enrichment)**: Injects institutional default execution metadata (`tick_size`, `lot_size`) for all candidates.
4.  **Stage 4 (Identity Deduplication)**: Removes redundant instruments (e.g. Spot vs Perp) for the same underlying asset. (Result: ~64 symbols).
5.  **Stage 5 (Statistical Selection)**: Executes Log-MPS 3.2 engine with ECI and Hurst vetoes. (Result: ~31 winners).

### 21.2 Secular Shorting Strategy
To profit from persistent downward drift in structurally weak assets, the platform includes a **Secular Shorting** layer. This scanner targets assets with:
- `Perf.1M < 0`: Confirmed monthly drawdown.
- `Hurst > 0.50`: Persistent, non-random drift.
- `ADX > 15`: Sufficient trend strength.

### 21.3 Forensic Data Alignment & The Inner Join Trap
A critical forensic discovery revealed that standard multi-asset covariance engines utilize a **Strict Inner Join** on return dates. While statistically conservative, this creates a "Trap" in high-growth portfolios (Crypto) where assets have asynchronous listing dates.

- **The Problem**: A single new listing (e.g. `PIPPIN`) can truncate the entire matrix to its listing day, silently dropping 80% of established alpha anchors (BTC, ETH) or macro benchmarks (SPY) because they don't share the same "Start Date" in a dense matrix.
- **The Fix (v3.2.9)**: The system implements **Robust Pairwise Correlation**. Hierarchical clustering now calculates linkage using every available overlapping session for each pair, rather than a global intersection.
- **The Guardrail**: To maintain significance, a `min_col_frac` of **0.05** (5% coverage) is enforced as a single source of truth in the `manifest.json`.

### 22. Balanced Alpha Selection & Factor Isolation
... (omitted) ...
-   **Forensic Rebalancing**: Standardized to **20 days** based on the Rebalance Sensitivity Audit (v3.2.7).

---

**Version**: 3.2.9  
**Status**: Production Certified  
**Last Updated**: 2026-01-11
