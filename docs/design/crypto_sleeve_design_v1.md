# Crypto Sleeve Design Document v3.2.4

## 1. Architecture Overview

### 1.1 System Context
The crypto sleeve operates as an independent capital allocation unit within the Fractal Risk Meta-Portfolio architecture, providing orthogonal exposure to digital assets while maintaining institutional-grade risk controls.

```
┌─────────────────────────────────────────────────────────────┐
│                    Meta-Portfolio Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Instruments  │  │     ETFs     │  │    Crypto    │      │
│  │   Sleeve     │  │    Sleeve    │  │    Sleeve    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │               │
│         └─────────────────┴──────────────────┘               │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │  Meta-HRP   │                          │
│                    │ Allocation  │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles
1. **BINANCE-Only Focus**: Highest liquidity, cleanest execution.
2. **Short-Cycle Momentum**: Daily/Weekly/Monthly (no 3M/6M anchors).
3. **Noise Floor Selection**: Filter white noise, delegate weighting to risk engines.
4. **Calendar Integrity**: 24x7 XCRY calendar with inner join for meta-portfolio.
5. **Barbell Risk**: Safe Haven anchors (90%) + Aggressors (10%).
6. **HRP Dominance**: Hierarchical Risk Parity as the primary stability profile.
7. **Temporal Alignment**: Rebalancing windows optimized via persistence analysis.
8. **Forensic Integrity**: 15-day rebalancing window as the structural standard for drawdown control.

---

## 21. Refinement Funnel Architecture

### 21.1 Liquidity Normalization & The Discovery Funnel
A forensic audit of global crypto liquidity reveals that raw screener metrics (`Value.Traded`) are not USD-normalized across currency pairs. Local fiat pairs (IDR, TRY, ARS) can dominate the rank with local-currency denominated volume, while DEX data remains highly contaminated by wash-trading noise.

To ensure institutional signal quality, the Discovery Layer implements a **Five-Stage Refinement Funnel**:
1.  **Stage 1 (Discovery)**: Fetches up to 5000 candidates sorted by raw liquidity from verified CEXs.
2.  **Stage 2 (USD-Normalization)**: Explicitly filters for institutional quote patterns (`USDT`, `USDC`, `FDUSD`) at the source. (Result: ~77 unique identities).
3.  **Stage 3 (Metadata Enrichment)**: Injects institutional default execution metadata (`tick_size`, `lot_size`, `price_precision`) for all candidates. This ensures that new listings are not vetoed due to latent exchange metadata.
4.  **Stage 4 (Identity Deduplication)**: Removes redundant instruments (e.g. Spot vs Perp) for the same underlying asset to ensure factor purity. (Result: ~64 refined candidates).
5.  **Stage 5 (Statistical Selection)**: Executes Log-MPS 3.2 engine with ECI and Hurst vetoes. (Result: ~36 winners).

**Volume Floors by Venue**:
-   **Spot**: $500,000.
-   **Perp**: $1,000,000.

**History & Lookback Alignment**:
The `crypto_production` profile aligns secular history lookback to **300 days** with a **90-day floor**. This ensures that TradFi macro anchors (`SPY`) achieve sufficient trading-day counts for covariance estimation while allowing high-momentum new listings to participate.

### 22. Balanced Alpha Selection & Factor Isolation
The Log-MPS 3.2 engine (Standard v3.2.4) implements high-fidelity factor isolation:
-   **High-Resolution Clustering (v3.2.4)**: The distance threshold for hierarchical clustering (Ward Linkage) is set to **0.50**. This isolates orthogonal risk units while maintaining semantic groupings (L1s, AI, Memes), allowing for a broader set of tradable candidates.
-   **Adaptive Friction Gate (v3.2.4)**: Applies a **25% Friction Budget Buffer** for assets with extreme alpha (> 100%). Additionally, the ECI hurdle is dynamically adjusted for turnaround plays (momentum > -0.5) to prevent blanket vetoes of high-potential reversals.
-   **Toxic Persistence Veto (v3.2.5)**: To protect against "Falling Knives," the engine disqualifies assets where $Hurst > 0.55$ and $Momentum < 0$. This ensures that assets with negative momentum are only included if they display mean-reverting characteristics ($H < 0.45$).
-   **Benchmark Stability Anchor (v3.2.6)**: Macro anchors (e.g., SPY) are exempt from Random Walk (Hurst) vetoes. This preserves the portfolio's low-beta offset even when the global equity market is in a non-trending regime.
-   **Rebalance Frequency**: Formally standardized to a **5-day rebalancing cycle** for the current regime, as recommended by the Forensic Persistence Audit ($T_{median}=5d$ for alpha drivers).
-   **Cluster Diversification**: Selects up to the **top 5 assets** per direction per cluster, ensuring deep factor representation across the candidate pool.

---

**Version**: 3.2.4  
**Status**: Production Certified  
**Last Updated**: 2026-01-10
