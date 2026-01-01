# Specification: Quantitative Strategy Archetypes (Jan 2026)

This document defines the formal technical standards for the core strategies and detection systems in the TradingView Scraper framework.

## 1. Antifragile Barbell Profile

The Barbell profile implements structural isolation between high-optionality alpha and a stable risk-balanced core.

| Component | standard | Rationale |
| :--- | :--- | :--- |
| **Aggressors (10%)** | Top 5 Assets by Antifragility Score | Captures high-optionality, convex returns. |
| **Core (90%)** | Optimized Core Sleeve | Prevents idiosyncratic decay of the overall portfolio. |
| **Core Engine** | `hrp` (Native skfolio) | Prioritizes absolute stability for the core foundation. |
| **Adaptive Scaling** | Regime-Aware Aggressor Weight | Reduces aggressor sleeve to 5% in `CRISIS` and expands to 15% in `QUIET`. |

## 2. Native Hierarchical Risk Parity (HRP)

The `hrp` profile provides the "capital preservation" standard using recursive tree-based bisection.

- **Algorithm**: Recursive Bisection (Native `skfolio` implementation).
- **Distance Metric**: **Pearson Correlation**.
- **Linkage Method**: **COMPLETE** (validated as the "Outstanding" configuration).
- **Risk Measure**: Variance.
- **Role**: Serves as the high-fidelity defensive baseline and the core optimization logic for the Barbell sleeve.

## 3. All Weather Quadrant Detector

The `MarketRegimeDetector` classifies market environments into four quadrants to drive adaptive strategy selection.

| Axis | System Proxy | Statistical Standard |
| :--- | :--- | :--- |
| **Growth Axis** | Annualized Return | Identifies Expansion vs. Contraction. |
| **Stress Axis** | Vol Ratio + DWT Noise | Identifies Stability vs. Turbulence. |

### The Quadrant Matrix:
1. **`EXPANSION`**: High Growth / Low Stress $\rightarrow$ **Adaptive Target**: `max_sharpe`.
2. **`INFLATIONARY_TREND`**: High Growth / High Stress $\rightarrow$ **Adaptive Target**: `barbell`.
3. **`STAGNATION`**: Low Growth / Low Stress $\rightarrow$ **Adaptive Target**: `min_variance`.
4. **`CRISIS`**: Low Growth / High Stress $\rightarrow$ **Adaptive Target**: `hrp`.

## 4. Institutional Fidelity Standards
- **Ledoit-Wolf Shrinkage**: Universal for all covariance-dependent steps.
- **L2 Regularization ($\gamma=0.05$)**: Universal guard against overfitting in all non-HRP optimizations.
- **Audit Requirement**: All transitions and weights must be recorded in the SHA-256 chained ledger.
