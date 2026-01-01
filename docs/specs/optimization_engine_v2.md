# Optimization Engine V2: Cluster-Aware Allocation

The Cluster-Aware Optimization Engine (v2) is an institutional-grade allocator designed to handle venue redundancy and enforce systemic risk controls across disparate asset classes.

## 1. Two-Layer Allocation Strategy

### Layer 1: Across Clusters (Factor Level)
The total capital is first distributed across high-level hierarchical risk buckets.
- **Max Cluster Cap (25%)**: Strictly enforced via linear constraints ($w_{cluster} \le 0.25$) to prevent systemic over-concentration in any single statistical factor.
- **Fragility Penalty**: Refactored objective functions (`min_var`, `max_sharpe`) now include a penalty term for clusters with high **Expected Shortfall (CVaR)**.
- **Turnover Control**: The custom engine implements an **L1-norm penalty** on weight changes relative to the previously implemented state (Gated by `feat_turnover_penalty`):
  $$Penalty_{Turnover} = \lambda \cdot \sum |w_{t} - w_{t-1}|$$

### Risk Profiles

#### 1. Hierarchical Risk Parity (HRP)
The HRP profile is implemented as a **Convex Risk Parity** optimization on cluster benchmarks:
- **Objective**: Minimize variance while forcing logarithmic weight penalties to ensure diversity across all discovered factors:
  $$Obj = 0.5 \cdot w^{T} \Sigma w - \frac{1}{n} \sum \log(w_{i})$$
- **Mathematical Rationale**: This approach avoids the instability of recursive bisection while achieving the same goal: ensuring that every cluster contributes to the portfolio's risk.

#### 2. Antifragile Barbell
The Barbell profile splits the portfolio into two distinct risk sleeves:
- **Aggressor Sleeve (5-15%)**: Allocates to clusters with the highest **Antifragility Scores** (convexity leaders). These are often high-momentum, high-volatility clusters.
- **Core Sleeve (85-95%)**: Allocates the remaining capital to the rest of the universe using the **HRP** profile for maximum stability.
- **Dynamic Scaling**: The aggressor weight is regime-dependent:
    - `QUIET`: 15%
    - `NORMAL`: 10%
    - `TURBULENT`: 8%
    - `CRISIS`: 5%

#### 3. Min Variance & Max Sharpe
Standard convex profiles with additional constraints:
- **Min Variance**: Pure risk minimization with cluster-level fragility penalties.
- **Max Sharpe**: Risk-adjusted return maximization using training window mean returns ($\mu$).
    - **Safety & Regularization**: To prevent "Ghost Alpha" (in-sample Sharpe > 10) and excessive churn:
        - **Turnover Penalty**: Mandatory L1-norm penalty on weight changes.
        - **Covariance Regularization**: L2 shrinkage applied to the covariance matrix to dampen noise.
        - **Objective Limit**: Optimization fails if the projected Sharpe exceeds realistic bounds (e.g., > 5.0), triggering a fallback to MinVariance.

#### 4. Equal Weight (Dynamic Baseline)
Used for isolated alpha attribution:
- **Raw Pool EW**: Equal allocation to all discovered candidates.
- **Filtered EW**: Equal allocation to all Top-N cluster leaders.
- **Rationale**: Provides a rigorous benchmark to measure the impact of weighting vs. selection.

### Layer 2: Intra-Cluster (Instrument Level)
Within each factor, weight is distributed using a **Momentum-Volatility Hybrid**:
- **Formula**: $Weight \propto 0.5 \cdot InverseVolatility + 0.5 \cdot AlphaRank$.
- **Rationale**: Ensures the portfolio is anchored by stable instruments while rewarding the highest-momentum members within a correlated group.

## 2. Risk Insulation (Barbell Strategy)

The Barbell strategy implements strict structural isolation:
- **Aggressor Sleeves**: Top 5 clusters by **Alpha Rank**.
- **Risk Insulation**: Any cluster selected for the high-optionality sleeve is **excluded** from the core optimization to ensure zero risk overlap.
- **Dynamic Regime Scaling**:
    - **QUIET**: 15% Aggressors / 85% Core.
    - **NORMAL**: 10% Aggressors / 90% Core.
    - **CRISIS**: 5% Aggressors / 95% Core.

## 3. Decision Support & Implementation

- **Lead Asset Designation**: The single best-performing member of each cluster is flagged for primary implementation.
- **Institutional Reporting**: Generates a professional dashboard with visual concentration bars and rebalancing BUY/SELL signals.
- **Audit Trace**: Every optimization run is logged in `selection_audit.json`, documenting the regime score and active constraints.
