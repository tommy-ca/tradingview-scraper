# Crypto Sleeve Design Document v1.9

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

## 16. Optimization Pipeline Hardening

### 16.1 Temporal Logic
The optimization pipeline implements a **Double-Step Lookahead** strategy:
- **Step Size**: 15 days.
- **Test Window**: 30 days.
- **Rationale**: Validating 2 consecutive steps per rebalance point ensures that momentum captures are not "flash-in-the-pan" anomalies but persistent regime transitions.

### 16.2 Alpha Capture Governance
The `SelectionEngineV32` is locked as the mandatory alpha core for crypto.
- **Score Type**: Log-Multiplicative Probability.
- **Filters**: Entropy (0.999), Hurst (0.48-0.52), Efficiency (0.15).

### 16.3 Dynamic Regime Adaptation (Phase 60 Update)
The optimization pipeline now features real-time adaptability via `optimize_clustered_v2.py`:
- **Regime Sensing**: Ingests `regime_analysis_v3.json` to detect market state (NORMAL, TURBULENT, CRISIS).
- **Cluster Cap Dynamic Scaling**:
    - **NORMAL**: 25% (Base Cap) - Allows conviction.
    - **TURBULENT**: 20% (Tightened) - Reduces idiosyncrasy.
    - **CRISIS**: 15% (Defensive) - Max diversification.
- **Metric Integration**: Embeds advanced Tail Risk (VaR, CVaR) and Alpha (Momentum, Dispersion) metrics into optimization metadata for auditability.

---

## 17. Portfolio Trails and Replay Rationale

### 17.1 The Nyquist Frequency of Rebalancing
A deep audit of Run `20260109-164834` confirms that the **15-day rebalancing window** acts as the Nyquist-sampling frequency for the crypto momentum cycle. 
- **Median Persistence**: $T_{median} = 19$ days.
- **Signal Capture**: Rebalancing at $T < T_{median}$ (specifically 15d) ensures that the system rotates out of assets before their momentum decays into high-entropy noise.
- **Friction-Alpha Parity**: Using 15 days provides sufficient alpha runway to overcome CEX commissions (4bps) and slippage (10bps) while maintaining a Sharpe > 2.0.

### 17.2 Replay Dynamics (The "Golden Path")
When replaying training and tests (Recursive Walk-Forward), the "trails" reveal a philosophy of **Philosophy-Consistent Diversification**:
1.  **Selection Path**: Filters remove 70% of discovered assets based on ECI (Efficiency Capture Index) vetoes.
2.  **Allocation Path**: HRP (Hierarchical Risk Parity) creates orthogonal risk units, ensuring that even if one cluster (e.g., Meme-Alts) collapses, the portfolio remains anchored in "Safe Haven" clusters (e.g., BTC/XMR).
3.  **Result**: The "Portfolio Trails" show consistent upward drift during expansionary regimes and horizontal stability during turbulent regimes, thanks to the dynamic cluster capping (reduction to 20% in turbulence).

---

### 17.3 Selection Evolution: The Freshness Factor
Analysis of the Q1 2026 runs demonstrates that **Data Freshness** is a primary alpha driver. 
- **Anchor Rotation**: When "Blue Chip" assets (BTC, SOL) are current, the Log-MPS v3.2 engine naturally favors them as low-entropy anchors.
- **Meme Pruning**: Speculative assets with high volatility but high ECI (friction) are vetoed when high-fidelity anchors provide a more efficient risk-adjusted path.
- **Structural Integrity**: The 15-day rebalancing window effectively "locks in" these rotations, preventing the portfolio from being stuck in stale discovery regimes.

---

## 18. Regime & Engine Performance Matrix (Window Replay)

### 18.1 Forensic Replay Analysis
A deep audit of the 7-window backtest simulation reveals distinct performance characteristics across market regimes:

| Regime Window | Characteristic | Winner | Loser | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Window 0 (Bear)** | Crash (-1.7 Sharpe) | **MinVar** (-1.5) | Benchmark (-1.8) | Defensive allocation minimized drawdown. |
| **Window 1 (Bull)** | Rally (+3.7 Sharpe) | **Market** (+3.7) | MinVar (+1.4) | High-beta exposure required for capture. |
| **Window 3 (Crash)** | Crisis (-2.6 Sharpe) | **MinVar** (-0.3) | Barbell (-2.7) | **Critical Insight**: MinVar's short hedging capabilities prevented catastrophic loss. |
| **Window 5 (Meme)** | Speculative (+3.3) | **Barbell** (+3.3) | Benchmark (+0.3) | Aggressor sleeve captured 1000x outliers. |
| **Window 6 (Turbulent)** | Choppy (-1.9) | **HRP (CVX)** (+1.9) | Benchmark (-1.9) | Hierarchical clustering isolated toxic clusters. |

### 18.2 Engine-Specific HRP Divergence
In Turbulent Window 6, HRP performance varied significantly by implementation:
- **CVXPortfolio**: **+1.98 Sharpe** (Superior covariance estimation).
- **Skfolio**: **+0.62 Sharpe** (Robust).
- **PyPortfolioOpt**: **-1.32 Sharpe** (Failed).

**Design Decision**: The production system shall prioritize **CVXPortfolio** and **Skfolio** for HRP implementations due to their superior handling of turbulent covariance matrices.

---

### 18.3 Engine Divergence Observation
In Turbulent Window 6, a significant divergence was observed between HRP implementations:
-   **PyPortfolioOpt (Single Linkage)**: -1.32 Sharpe.
-   **Custom/CVX (Ward Linkage)**: +1.98 Sharpe.

**Hypothesis**: Ward Linkage may be more robust to crypto noise.
**Strategy**: Maintain an open tournament matrix including all engines to validate this hypothesis across a wider sample of regimes (N > 30 windows) before deprecating any implementation.

---

### 18.4 Selection Funnel Dynamics
Audit of the Q1 2026 Production Run confirms the "Natural Selection" funnel architecture:
-   **Discovery**: ~100 assets.
-   **Retention**: ~20% (21 assets).
-   **Veto Architecture**:
    -   **High Friction (50%)**: Removes assets where ECI > 0.1 and Momentum < 0.
    -   **Low Efficiency (32%)**: Removes assets with Efficiency Ratio < 0.05.
    -   **Random Walk (18%)**: Removes assets with Hurst exponent ~0.5.

This funnel ensures that the *inputs* to the Optimization Engine are already pre-qualified as "High Quality Alpha Candidates", allowing the optimizer to focus on correlation management rather than quality control.

---

### 19. Data Lifecycle & Retention
To maintain high-fidelity performance without storage bloat:
-   **Active Window**: The system retains the last **10 production runs** in the active workspace for immediate audit and rollback.
-   **Archival Policy**: Runs older than 10 iterations are automatically compressed (`tar.gz`) and moved to `artifacts/archive/` via the `make clean-archive` target.
-   **Traceability**: Even archived runs retain their `audit.jsonl` integrity, ensuring full regulatory compliance capability.

---

**Version**: 2.7  
**Status**: Production Ready  
**Last Updated**: 2026-01-09
