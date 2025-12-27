# Optimization Engine V2: Cluster-Aware Allocation

The Cluster-Aware Optimization Engine (v2) is an institutional-grade allocator designed to handle venue redundancy and enforce systemic risk controls across disparate asset classes.

## 1. Two-Layer Allocation Strategy

### Layer 1: Across Clusters (Factor Level)
The total capital is first distributed across high-level hierarchical risk buckets.
- **Max Cluster Cap (25%)**: Strictly enforced to prevent systemic over-concentration.
- **Fragility Penalty**: Refactored objective functions (`min_var`, `max_sharpe`) now include a penalty term for clusters with high **Expected Shortfall (CVaR)**.
- **Net vs Gross Exposure**: The engine tracks both total capital at risk (Gross) and directional tilt (Net) for each factor.

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
