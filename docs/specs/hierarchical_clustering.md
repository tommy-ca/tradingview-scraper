# Hierarchical Clustering & Risk Bucketing

This specification documents the methodology for grouping correlated assets into hierarchical risk buckets to prevent capital concentration in redundant factors.

## 1. Distance Metric

The engine uses **Correlation Distance** as the primary similarity metric:
$$d_{i,j} = \sqrt{0.5 \times (1 - \rho_{i,j})}$$
- **$\rho_{i,j}$**: Pearson correlation between assets $i$ and $j$.
- **Range**: $[0, 1]$, where $0$ is perfectly correlated and $1$ is perfectly anti-correlated.

## 2. Hierarchical Linkage

- **Algorithm**: **Average Linkage** (or Ward).
- **Process**: Builds a dendrogram (tree) by recursively merging the closest pairs of clusters.
- **Tree Cutting**: The tree is "cut" at a global distance threshold (Default: **0.4**, approx. 70% correlation) to produce flat clusters (Risk Buckets).

## 3. Nested Sub-Clustering

For large clusters (e.g., the Crypto Hub with 60+ assets), the engine performs a second pass of analysis to reveal internal venue and instrument redundancy.
- **Trigger**: Any cluster with more than 10 assets.
- **Sub-Threshold**: **0.2** (approx. 92% correlation).
- **Goal**: Group identical underlying assets across different exchanges (e.g., SOL-Binance, SOL-OKX, SOL-Bybit) into their own sub-buckets.

## 4. Metadata Propagation

To make clusters actionable, the following metadata is tracked:
- **Cluster ID**: Numeric identifier.
- **Primary Sector**: The dominant sector label within the bucket.
- **Lead Asset**: The asset with the lowest volatility (or highest intra-cluster weight), used as the primary execution ticker.
- **Market Coverage**: List of all unique markets (e.g., FOREX, BOND_ETF, BINANCE_PERP) represented in the bucket.

## 5. Rationale for Bucketing

- **Redundancy Filter**: Prevents the portfolio from over-allocating to a sector simply because it has many available tickers (common in Crypto and Equities).
- **Uncorrelated Anchor Identification**: Easily spots "solitary" clusters (buckets with size 1) that provide unique, uncorrelated risk premiums.
