# Optimization Engine V2: Cluster-Aware Allocation

The Cluster-Aware Optimization Engine (v2) is designed to handle asset redundancy and enforce systemic diversification by grouping correlated symbols into hierarchical risk buckets before allocating capital.

## 1. Two-Layer Allocation Strategy

The engine utilizes a top-down approach to portfolio construction:

### Layer 1: Across Clusters (Systemic)
The total portfolio weight (100%) is first distributed across the discovered hierarchical clusters.
- **Profiles Supported**: 
    - **Min Variance**: Global Minimum Variance across synthetic cluster returns.
    - **Risk Parity**: Equal Risk Contribution from every cluster.
    - **Max Sharpe**: Maximum Sharpe ratio based on cluster benchmarks.
- **Constraint**: A **Global Cluster Cap (Default: 25%)** is enforced at this level. No single economic factor can dominate more than a quarter of the portfolio.

### Layer 2: Intra-Cluster (Robustness)
Within each cluster, the assigned weight is distributed among its members.
- **Methodology**: **Inverse-Variance Weighting**.
- **Rationale**: This favors the most stable asset or exchange venue within a correlated group (e.g., picking the lowest-volatility BTC venue in a Crypto cluster).

## 2. Risk Insulation (Barbell Strategy)

For the Antifragile Barbell profile, the engine enforces strict structural isolation:
- **Aggressor Identification**: Top 5 clusters by **Antifragility Score** (Composite of Positive Skew and Tail Gain).
- **Core Optimization**: The 90% "Safe Core" is optimized using Clustered Risk Parity across all clusters **excluding** those used in the Aggressor sleeve.
- **Sleeve Weights**: 
    - **10% Aggressors** (Fixed split across 5 unique buckets).
    - **90% Core** (Diversified across remaining uncorrelated factors).

## 3. Implementation Heuristics

- **Lead Asset Selection**: The asset with the highest weight within its cluster is designated as the "Lead Asset" for execution.
- **Small Portfolio Safety**: Upper bounds for weights are dynamically adjusted (`max(0.2, 1.1 / n_assets)`) to ensure optimization convergence even when the number of core assets is low.
- **Redundancy Filter**: Prevents "ticker counting" from biasing the portfolio toward sectors with many available symbols (e.g., Crypto).
