# Specification: Selection Intelligence (V1)
**Status**: Formalized
**Date**: 2025-12-31

## 1. Overview
Selection Intelligence defines the logic for "Pruning" the raw discovered candidate pool into a high-quality implementation universe. It uses hierarchical clustering to ensure diversification and multi-lookback alpha scoring to select leaders.

## 2. Hierarchical Pruning

### 2.1 Cluster Discovery
- **Linkage**: Ward Linkage on a distance matrix derived from robust correlations.
- **Multi-Lookback**: Correlations are averaged over 60d, 120d, and 200d windows to ensure statistical stability.
- **Adaptive Threshold**: Uses a distance threshold (default 0.5) to determine the number of clusters, ensuring that assets in different clusters are sufficiently uncorrelated.

### 2.2 Execution Alpha Scoring
Assets within each cluster are ranked using a composite score:
- **Momentum (30%)**: Global Cross-Sectional Percentile Rank of annualized returns.
- **Stability (20%)**: Inverse volatility rank.
- **Antifragility (20%)**: Convexity/Tail-risk rank (PIT Audit).
- **Liquidity (30%)**: Relative volume and spread proxies.

### 2.3 Intra-Cluster Selection (Top N)
- **Identity Deduplication**: Canonical identities (e.g., Binance BTC and Bybit BTC) are merged; only the most liquid/stable venue is selected.
- **Leader Selection**: Selects the **Top N** (default 2) assets per cluster.
- **Dynamic Capacity**: (Future) Scale N based on cluster internal variance.

## 3. Integration with Risk Profiles

| Profile | Selection Strategy | Rationale |
| :--- | :--- | :--- |
| **HRP** | Diversified Top N | HRP benefits from having diverse cluster leaders to distribute risk. |
| **Barbell** | Convexity Leaders | Selection prioritizes assets with high Antifragility scores for the Aggressor sleeve. |
| **MinVar** | Stability Leaders | Selection favors low-volatility leaders within clusters. |

## 4. Pipeline implementation
Selection is performed in Step 5 of the production pipeline via `scripts/natural_selection.py`. It produces the `portfolio_candidates.json` artifact which serves as the "Ground Truth" for all optimization engines.
