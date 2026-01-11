# Crypto Sleeve Design Document v3.3.0

## 1. Architecture Overview

### 1.1 System Context
The crypto sleeve operates as an independent capital allocation unit within the Fractal Risk Meta-Portfolio architecture, providing orthogonal exposure to digital assets while maintaining institutional-grade risk controls.

### 1.2 Design Principles
1. **Directional Normalization**: All returns are transformed to "Synthetic Longs" prior to analysis.
2. **Short-Cycle Momentum**: 20-day rebalancing window as the structural standard.
3. **Noise Floor Selection**: Late-binding trend filters to reject "dead-cat bounces."
4. **HRP Dominance**: Hierarchical Risk Parity as the primary stability profile.
5. **Temporal Alignment**: Distance matrices averaged across 60d, 120d, and 200d windows.

---

## 22. Synthetic Long Normalization & Directional Purity (v3.3.0)
To ensure that all quantitative models (Selection, HRP, MVO) operate with maximum consistency across Long and Short regimes, the platform enforces **Synthetic Long Normalization**:

1.  **Late-Binding Direction**: At each rebalance boundary (production or backtest window), the system calculates the recent momentum ($M$) for every candidate.
2.  **Alpha Alignment**: The raw returns matrix ($R_{raw}$) is transformed into an alpha-aligned matrix ($R_{\alpha}$):
    - If $M > 0$, asset is **LONG**; $R_{\alpha} = R_{raw}$
    - If $M < 0$, asset is **SHORT**; $R_{\alpha} = -1 \times R_{raw}$
3.  **Model Invariance**: Portfolio engines receive the $R_{\alpha}$ matrix. Because all assets now display positive expected returns, HRP and MVO models correctly reward stable price trends regardless of their physical direction. This eliminates the need for direction-aware code paths in the optimizers.
4.  **Forensic Replay**: The assigned direction and synthetic weights are recorded in the `audit.jsonl` ledger, enabling full reconstruction of the `Net_Weight` ($W_{net} = W_{synthetic} \times \text{sign}(M)$).

#### 22.1 Rationale for Universal Normalization
By moving directional logic to a single "Normalization Layer" prior to analysis, we achieve:
- **Factor Stability**: HRP can correctly group and weight persistent downtrends (Shorts) based on their stability.
- **Unified Backtesting**: Simulators treat all optimized weights as "Commitment to Alpha," with sign-correction handled only at the final trade execution step.
- **Consistent Selection**: Selection engines (Log-MPS) evaluate "Alpha Quality" (Efficiency, Entropy, Hurst) on the synthetic uptrend, ensuring symmetric standards for Long and Short signals.

---

**Version**: 3.3.0  
**Status**: Production Hardened  
**Last Updated**: 2026-01-11
