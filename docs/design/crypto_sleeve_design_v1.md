# Crypto Sleeve Design Document v3.3.1

## 1. Architecture Overview

### 1.1 System Context
The crypto sleeve operates as an independent capital allocation unit within the Fractal Risk Meta-Portfolio architecture, providing orthogonal exposure to digital assets while maintaining institutional-grade risk controls.

### 1.2 Design Principles
1. **Directional Normalization**: All returns are transformed to "Synthetic Longs" prior to analysis.
2. **Short-Cycle Momentum**: 20-day rebalancing window as the structural standard.
3. **Noise Floor Selection**: Late-binding trend filters to reject "dead-cat bounces."
4. **HRP Dominance**: Hierarchical Risk Parity as the primary stability profile.
5. **Temporal Alignment**: Distance matrices averaged across 60d, 120d, and 200d windows.
6. **Deep Auditability**: Full matrix transparency via window-by-window forensic reports.

---

## 21. Refinement Funnel Architecture

### 21.1 Liquidity Normalization & The Discovery Funnel
A forensic audit of global crypto liquidity reveals that raw screener metrics (`Value.Traded`) are not USD-normalized across currency pairs. Local fiat pairs (IDR, TRY, ARS) can dominate the rank with local-currency denominated volume.

To ensure institutional signal quality, the Discovery Layer implements a **Five-Stage Refinement Funnel**:
1.  **Stage 1 (Discovery)**: Fetches up to 5000 candidates sorted by raw liquidity from verified CEXs. (Result: ~214 symbols).
2.  **Stage 2 (Normalization)**: Explicitly filters for institutional quote patterns (`USDT`, `USDC`, `FDUSD`) at the source. (Result: ~108 symbols).
3.  **Stage 3 (Metadata Enrichment)**: Injects institutional default execution metadata (`tick_size`, `lot_size`) for all candidates.
4.  **Stage 4 (Identity Deduplication)**: Removes redundant instruments (e.g. Spot vs Perp) for the same underlying asset. (Result: ~64 symbols).
5.  **Stage 5 (Statistical Selection)**: Executes Log-MPS 3.2 engine with ECI and Hurst vetoes. (Result: ~31 winners).

---

## 22. Synthetic Long Normalization & Directional Purity (v3.3.0)
To ensure that all quantitative models (Selection, HRP, MVO) operate with maximum consistency across Long and Short regimes, the platform enforces **Synthetic Long Normalization**:

1.  **Late-Binding Direction**: At each rebalance boundary (production or backtest window), the system calculates the recent momentum ($M$) for all candidates.
2.  **Alpha Alignment**: The raw returns matrix ($R_{raw}$) is transformed into an alpha-aligned matrix ($R_{\alpha}$):
    - If $M > 0$, asset is **LONG**; $R_{\alpha} = R_{raw}$
    - If $M < 0$, asset is **SHORT**; $R_{\alpha} = -1 \times R_{raw}$
3.  **Model Invariance**: Portfolio engines receive the $R_{\alpha}$ matrix. Because all assets now display positive expected returns, HRP and MVO models correctly reward stable price trends regardless of their physical direction. This eliminates the need for direction-aware code paths in the optimizers.
4.  **Forensic Replay**: The assigned direction and synthetic weights are recorded in the `audit.jsonl` ledger, enabling full reconstruction of the `Net_Weight` ($W_{net} = W_{synthetic} \times \text{sign}(M)$).

---

## 23. Deep Forensic reporting (v3.3.1)
To support institutional compliance and quantitative transparency, the system generates a **Deep Full Analysis & Audit Report**:
- **Funnel Trace**: Step-by-step retention metrics for the Five-Stage Funnel.
- **Risk Matrix**: Performance comparison across 153 engine/profile/simulator combinations.
- **Window Audit**: Trace of rebalance events, including assigned directions and top holdings.
- **Outlier Logic**: Automated Z-score identification of performance deviations.

---

**Version**: 3.3.1  
**Status**: Production Certified  
**Last Updated**: 2026-01-11
