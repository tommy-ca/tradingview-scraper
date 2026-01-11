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

### 22. Balanced Alpha Selection & Factor Isolation
The Log-MPS 3.2 engine (Standard v3.2.8) implements:
-   **High-Resolution Clustering (v3.2.4)**: Ward Linkage distance threshold set to **0.50**.
-   **Adaptive Friction Gate (v3.2.4)**: 25% Friction Budget Buffer for extreme alpha drivers.
-   **Toxic Persistence Veto (v3.2.5)**: Disqualifies assets where $Hurst > 0.55$ and $Momentum < 0$ (unless identified as mean-reverting shorts).
-   **Benchmark Stability Anchor (v3.2.6)**: Macro anchors (SPY) are exempt from Random Walk vetoes.
-   **Forensic Rebalancing**: Standardized to **20 days** based on the Rebalance Sensitivity Audit (v3.2.7), which identified it as the Sharpe-optimal window for the current cross-asset regime.

---

**Version**: 3.2.8  
**Status**: Production Certified  
**Last Updated**: 2026-01-10
