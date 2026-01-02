# Research Report: Battle of Architectures 2026
**Date**: 2026-01-02
**Status**: Formalized - v2.1 Crowned Standard

## 1. Executive Summary
This research track benchmarked three distinct asset selection architectures across the full 2025 continuous walk-forward matrix. The goal was to determine if **Multiplicative Probabilities (v3.x)** or **Additive Rank-Sum (v2.x)** models provide superior risk-adjusted alpha when enhanced with spectral predictability metrics.

**Final Result**: **Selection v2.1 (Tuned Additive)** outperformed all models in risk-adjusted terms, achieving a **Sharpe Ratio of 3.75**, surpassing the previous v3.1 benchmark (3.55).

## 2. Architecture Comparison

| Model | Logic | Predictability | Weights | Realized Sharpe |
| :--- | :--- | :--- | :--- | :--- |
| **v3.1** | Multiplicative | Vetoes Only | Unit | 3.55 |
| **v3.2** | Log-MPS | Integrated Sum | HPO Tuned | 2.96 |
| **v2.1** | Additive Rank | Integrated Sum | HPO Tuned | **3.75** |

## 3. Key Findings

### 3.1 The Superiority of Additive Ranks
While Multiplicative models (v3.x) are excellent at "Darwinian" pruning (killing bad assets), they tend to be over-aggressive in concentration. Additive models (v2.1) act as a structural hedge; by summing ranks, the system identifies assets that are "all-rounders" (good momentum AND good predictability AND good stability), leading to significantly lower portfolio volatility (8.7% vs 10.4%).

### 3.2 HPO Weight Attribution (v2.1)
The Optuna study identified that in 2025, **Survival** and **Momentum** were the dominant additive drivers, while **Hurst** was de-emphasized:

- **Momentum**: 0.9070
- **Survival**: 0.8690
- **Entropy (Noise Reduction)**: 0.3911
- **Efficiency (Chop Reduction)**: 0.2946
- **Antifragility**: 0.2429

### 3.3 Turnover Stability
Additive models proved more stable than Log-MPS models. `v2.1` maintained a turnover profile (0.35) close to the baseline `v3.1` (0.33), while providing a much smoother equity curve.

## 4. Conclusion & Deployment Recommendation
**Selection v2.1 is promoted to the Production Standard.** 
It successfully integrates 2026 spectral metrics into a robust, scale-invariant additive model. The transition from "Pruning" (Multiplicative) to "Scoring" (Additive) has yielded a +0.20 improvement in Sharpe ratio.

**Action**: Implementers should prefer `v2.1` for all risk-parity and diversified profiles. `v3.1` remains an alternative for ultra-aggressive "aggressor" wings of a Barbell.
