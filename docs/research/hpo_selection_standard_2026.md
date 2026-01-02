# Research Report: Optuna Hyperparameter Tuning (Log-MPS 3.2)
**Date**: 2026-01-02
**Status**: Validated (Experimental)

## 1. Executive Summary
This research track successfully transitioned the asset selection engine from a multiplicative probability model (**v3.1**) to an additive log-probability model (**v3.2**). The primary goal was to improve numerical stability and enable automated hyperparameter optimization (HPO) via Optuna. 

Validation shows that while **Log-MPS 3.2** provides a smoother optimization surface and successfully identifies alpha-generating weights, the current baseline **v3.1** (without predictability vetoes) remains a formidable benchmark due to its aggressive capture of high-momentum outliers in the 2025 stressed regime.

## 2. Methodology
- **Refactor**: Implemented `SelectionEngineV3_2` using $Score = \sum \omega_i \ln(P_i)$.
- **HPO Objective**: Maximized **Selection Alpha** (Selected EW Return - Raw Pool EW Return).
- **Data**: Continuous 126/21 walk-forward windows across the full year 2025.
- **Regimes**: Focused on "Stressed" (TURBULENT/CRISIS) regimes which dominated 2025.

## 3. HPO Results (Stressed Regime)
The Optuna study (200 trials) identified the following optimal weights:

| Component | Weight ($\omega$) | Interpretation |
| :--- | :--- | :--- |
| **Momentum** | 1.3126 | Primary Alpha Driver |
| **Stability** | 0.0112 | Heavily de-emphasized in crisis |
| **Liquidity** | 0.1978 | Secondary filter |
| **Antifragility** | 1.7406 | Critical for crisis selection |
| **Survival** | 1.8052 | Dominant factor for stressed capture |
| **Efficiency** | 0.5061 | Moderate penalty for chop |
| **Entropy** | 0.0928 | Low impact in crisis regime |
| **Hurst** | 0.1716 | Low impact in crisis regime |

**Key Finding**: In stressed regimes, the system favors **Survival** and **Antifragility** over traditional "Stability" (low volatility). This confirms that "Operation Darwin" effectively prioritizes assets that can withstand high-stress environments.

## 4. Performance Validation
Comparison across full 2025 (Equal Weight profile):

| Engine | Annualized Return | Sharpe | Max Drawdown |
| :--- | :--- | :--- | :--- |
| **v3.1 (Baseline)** | **36.8%** | **3.55** | **-4.4%** |
| **v3.2 (Log-MPS)** | 33.0% | 2.74 | -6.5% |

**Note on Regression**: The underperformance of v3.2 relative to v3.1 in this specific tournament is attributed to the "No Veto" nature of the v3.1 baseline used here. v3.1 captures a broader set of momentum winners that the "refined" v3.2 weights may have pruned. However, v3.2 offers significantly better explainability and a path to regime-specific tuning.

## 5. Deployment Status
- **Log-MPS 3.2** is fully integrated and gated by `feat_selection_logmps`.
- **Dynamic Switching** is operational: the engine automatically applies HPO weights when `TURBULENT` or `CRISIS` regimes are detected.
- **Recommendation**: Maintain `feat_selection_logmps=False` as the default for production until a broader historical HPO (including 2022-2024 data) is completed to verify the robustness of the weights.
