# Crypto Sleeve Design Document v3.2.13

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
5.  **Stage 5 (Statistical Selection)**: Executes Log-MPS 3.2 engine with ECI and Hurst vetoes. (Result: ~35 winners).

### 21.2 Secular Shorting Strategy
To profit from persistent downward drift in structurally weak assets, the platform includes a **Secular Shorting** layer. This scanner targets assets with:
- `Perf.1M < 0`: Confirmed monthly drawdown.
- `Hurst > 0.50`: Persistent, non-random drift.
- `ADX > 15`: Sufficient trend strength.

### 22. Balanced Alpha Selection & Factor Isolation
The Log-MPS 3.2 engine (Standard v3.2.13) implements:
-   **High-Resolution Clustering (v3.2.4)**: Ward Linkage distance threshold set to **0.50**.
-   **Adaptive Friction Gate (v3.2.4)**: 25% Friction Budget Buffer for extreme alpha drivers.
-   **Toxic Persistence Veto (v3.2.5)**: Disqualifies assets where $Hurst > 0.55$ and $Momentum < 0$ (unless identified as mean-reverting shorts).
-   **Benchmark Stability Anchor (v3.2.6)**: Macro anchors (SPY) are exempt from Random Walk vetoes.
-   **Forensic Rebalancing**: Standardized to **20 days** based on the Rebalance Sensitivity Audit (v3.2.7).

### 23. Hierarchical Cluster Analysis (HRP Core)
Hierarchical clustering (Ward Linkage on Robust Pairwise Correlation) serves as the structural foundation for both Selection and Allocation:

1. **Selection Integration**: The `Natural Selection` engine groups candidates by factor identity. It applies a **Top-N-per-Cluster** limit (Standard: 5) to prevent a single idiosyncratic factor from starving the rest of the portfolio's factor representation.
2. **Allocation Integration**: The `Clustered Optimizer` uses the dendrogram to enforce **Factor-Level Risk Caps** (25% per cluster). Even if a single asset has superior Sharpe, the system restricts total factor exposure to maintain orthogonal risk units.
3. **Stability Protocol (v3.2.10)**: To prevent cluster "jitter" during regime shifts, distance matrices are calculated across three horizons (60d, 120d, 200d) and averaged. Ward Linkage is then applied to the averaged matrix, prioritizing cluster cohesion and reducing sensitivity to short-term microstructural noise.

### 25. Metadata Enrichment & Isolation Integrity (v3.2.14)
To eliminate technical vetoes and ensure pure alpha exposure, the pipeline enforces a strict enrichment and isolation sequence:

1.  **Pre-Selection Enrichment**: All candidates are enriched with institutional metadata (e.g. `tick_size`, `lot_size`) immediately after ingestion. This guarantees that new listings without full exchange metadata are not rejected by the `SelectionEngine`.
2.  **Selection Isolation**: During the selection phase, macro benchmarks (SPY) are explicitly removed from the winner's list to prevent "beta pollution" in the alpha universe.
3.  **Post-Selection Integrity**: The `BacktestEngine` re-introduces benchmarks solely for comparative baselines (`market`, `benchmark` profiles) while keeping risk-optimized profiles (`max_sharpe`, `hrp`) pure.

---

**Version**: 3.2.14  
**Status**: Production Certified  
**Last Updated**: 2026-01-11
