# Multi-Engine Optimization Benchmarks

This specification defines the integration of advanced portfolio optimization libraries into the production pipeline. The goal is to provide a comparative framework between the current custom `ClusteredOptimizerV2` and established institutional-grade engines.

## 1. Integrated Engines

The following engines will be implemented using a unified `BaseRiskEngine` interface:

| Engine | Primary Implementation | Profile Focus |
| :--- | :--- | :--- |
| **skfolio** | `skfolio.optimization` | Hierarchical Risk Parity (HRP), Max Diversification |
| **Riskfolio-Lib** | `riskfolio.Portfolio` | Minimum CVaR, Tail Risk Optimization |
| **PyPortfolioOpt** | `pypfopt.efficient_frontier` | Standard Mean-Variance (MVO), Shrinkage Models |
| **CVXPortfolio** | `cvxportfolio.Policy` | Multi-Period Optimization (MPO), Cost-Aware Weights |

## 2. Standardized Portfolio Profiles

Four institutional profiles will be benchmarked across all engines:

### A. Minimum Variance (MinVar)
*   **Goal**: Minimize total portfolio volatility.
*   **Constraint**: No short selling, long-only weights sum to 1.
*   **Enhancement**: Apply Ledoit-Wolf shrinkage to covariance matrices where applicable.

### B. Hierarchical Risk Parity (HRP)
*   **Goal**: Allocate capital based on the hierarchical structure of correlations.
*   **Engine Preference**: `skfolio` and `Riskfolio-Lib` native HRP implementations.
*   **Rationale**: Robustness to covariance matrix noise and instability.

### C. Maximum Sharpe (MaxSharpe)
*   **Goal**: Maximize the risk-adjusted return (mean return / volatility).
*   **Enhancement**: Use high-integrity 200-day returns for mean estimation.
*   **Constraint**: Enforce 25% cluster cap to prevent "corner solution" concentration.

### D. Antifragile Barbell (Barbell)
*   **Goal**: Structural isolation between high-optionality "Aggressors" and stable "Core".
*   **Sleeve Allocation**: 10% Aggressors (Top 5 Alpha Rank) / 90% Core.
*   **Core Engine**: The 90% Core sleeve will be optimized using the selected engine's `MinVar` or `RiskParity` logic.

## 3. Benchmarking Framework

### Walk-Forward Validation (Tournament Mode)
The `BacktestEngine` will be extended to run a "Tournament Mode":
1.  **Training Window**: 120 Days.
2.  **Test Window**: 20 Days.
3.  **Metrics**: 
    *   Annualized Sharpe Ratio
    *   Maximum Drawdown (MDD)
    *   Conditional Value at Risk (CVaR @ 95%)
    *   Win Rate
    *   Turnover (Stability of weights)

### Artifact Generation
For each run, the pipeline will generate:
- `portfolio_optimized_<engine>.json`: The recommended weights for implementation.
- `tournament_results.json`: Consolidated performance comparison.
- `engine_comparison_report.md`: Markdown summary with performance rankings.

## 4. Implementation Constraints
*   **Cluster Awareness**: All engines must respect the **Volatility Hierarchical Clusters** generated in Step 9 of the production pipeline.
*   **Liquidity Guard**: Minimum weight floor of 0.1% and maximum cap of 25% per cluster.
*   **Execution Intelligence**: Engines should prioritize assets with higher `Alpha Score` (Liquidity + Momentum + Convexity) when multiple options exist within a cluster.
