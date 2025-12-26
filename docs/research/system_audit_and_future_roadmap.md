# Quantitative Pipeline Audit & Strategic Roadmap

This document consolidates findings from the 2025-12-26 system audit and outlines the strategic plan for Phase 5 development to enhance the operability and robustness of the portfolio generation lifecycle.

## 1. Executive Summary
The current system has successfully implemented a multi-asset, cluster-aware quantitative pipeline. It excels at handling asset redundancy and identifying secular regimes. However, the system relies on static thresholds and lacks automated rebalancing tracking ("State Management"), which limits its effectiveness in fast-moving market regimes.

## 2. Audit Findings: Identified Weaknesses

### Stage 1: Discovery & Selection
- **Fixed Diversity Caps**: The system picks the Top 10 assets per category regardless of the sector's current alpha density.
- **Metadata Timing**: Metadata enrichment occurs *after* selection, leading to a risk of "blind" clustering if descriptions are missing during the initial grouping.

### Stage 2: Data Resilience
- **Rigid Lookback**: All assets are forced to a 200-day window. Recently listed high-momentum assets (e.g., new Crypto Perps) may be dropped due to insufficient history even if they provide unique diversification.
- **Throttling Inefficiency**: Backfill batching is static. There is no automated "slow-lane" fallback for problematic exchanges.

### Stage 3: Hierarchical Analysis
- **Static Cutting Threshold**: The 0.4 correlation distance threshold is used for all market conditions. It does not tighten during "Correlation One" spikes.
- **Labeling Noise**: While mode-selection was added, some mixed clusters still suffer from inconsistent sector labeling.

### Stage 4: Risk Optimization
- **Binary Fragility**: Fragility scores are calculated and reported but do not influence the optimization objective function (Weights are not penalized by fragility).
- **Uniform Intra-Cluster Weighting**: Weight distribution within a bucket is purely Inverse-Variance, ignoring current momentum or alpha ranking for sizing.

## 3. Phase 5 Roadmap: Dynamic Constraints & State Management

### A. Dynamic Risk Constraints (Priority: High)
- **Fragility-Adjusted Objective**: Penalize clusters with high CVaR (Expected Shortfall) directly in the optimizer.
- **Regime-Adaptive Clustering**: Automatically adjust the distance threshold ($t$) based on the `Regime_Score`:
    - `CRISIS`: $t = 0.3$ (Higher diversification forced)
    - `NORMAL`: $t = 0.4$
    - `QUIET`: $t = 0.5$ (Allow larger, thematic buckets)

### B. Alpha-Weighted Internal Distribution (Priority: High)
- **Hybrid Layer 2**: Replace pure Inverse-Variance with a blend:
    - $Weight = 0.5 \cdot \text{InvVar} + 0.5 \cdot \text{MomentumRank}$
    - This ensures that the Lead Asset doesn't just represent the "stablest" member but also the most "active" member.

### C. State-Aware Workflows (Priority: Medium)
- **Portfolio State Engine**: Implement `scripts/track_portfolio_state.py` to compare "Current Optimal" vs. "Last Implemented" and report **Rebalancing Drift**.
- **Selective Sync**: Update `make prep` to only backfill assets that are stale or missing, rather than checking the entire universe, improving throughput by 60%+.

### D. Advanced Signal Fusion (Priority: Low)
- **Inter-Market Sentiment**: Use G8 Forex trend strength as a global multiplier for Crypto/Equity exposure limits.

## 4. Operational Improvement Suggestions

1. **Recovery Loops**: Implement a `make recover` target that specifically identifies failed backfills from the previous run and re-tries them with a batch size of 1.
2. **Institutional Guardrails**: Integrate `make audit` into a pre-commit hook or GitHub Action to ensure no logic change breaches the 25% systemic cap.
3. **Threshold Sensitivity Analysis**: Create a script to visualize how the number of clusters changes as the distance threshold moves from 0.1 to 0.9.

## 5. Next Steps
1. Refactor `optimize_clustered_v2.py` to support **Fragility Penalties**.
2. Implement the **Selective Sync** logic in `prepare_portfolio_data.py`.
3. Scaffold the **Portfolio State Engine** to track drift.
