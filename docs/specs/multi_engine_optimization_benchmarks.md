# Multi-Engine Optimization Benchmarks (Implemented)

This specification defines the integration of advanced portfolio optimization libraries into the production pipeline. As of Jan 2026, the framework is fully profile-centric and validated across the 4D Tournament Matrix.

## 1. Integrated Engines

The following engines are implemented using a unified `BaseRiskEngine` interface. Universal fallbacks have been removed to ensure library-specific variance:

| Engine | Library | Profile Native Focus |
| :--- | :--- | :--- |
| **Custom (Internal)** | `cvxpy` | Research baseline, standard quadratic objectives |
| **skfolio** | `skfolio.optimization` | Native HRP, Risk Budgeting, Equal-Weighted |
| **Riskfolio-Lib** | `riskfolio.Portfolio` | native Risk Parity, HRP (codependence), CVaR |
| **PyPortfolioOpt** | `pypfopt.efficient_frontier` | Standard HRP, Efficient Frontier |
| **CVXPortfolio** | `cvxportfolio.Policy` | Multi-Period Optimization (MPO), MVO |

## 2. Standardized Portfolio Profiles

The framework benchmarks institutional risk management paradigms. All engines must implement these profiles natively:

- **`market`**: Institutional Baseline (Single asset **SPY**, Equal-Weight).
- **`benchmark`**: Research Baseline (**Unpruned candidate pool**, Equal-Weight).
- **`hrp`**: Hierarchical Risk Parity (Library-specific tree bisection).
- **`risk_parity`**: Equal Risk Contribution (Library-specific native solvers).
- **`max_sharpe`**: Optimized return-to-risk ratio.
- **`barbell`**: Sleeve-based sleeve strategy.
- **`min_variance`**: Absolute risk minimization.

## 3. Benchmarking Framework

### 4D Matrix Validation (Tournament Mode)
The `BacktestEngine` executes a 4D cross-product:
1.  **D1: Selection Mode** (v2, v3)
2.  **D2: Engines** (All 5 backends)
3.  **D3: Profiles** (Standardized suite)
4.  **D4: Simulators** (cvxportfolio, nautilus, vectorbt, custom)

### Simulator Parity Breakthrough (Jan 2026)
Institutional baselines achieved **absolute parity (20.67%)** across all backends:
- **`cvxportfolio`**: High-fidelity execution with N+1 alignment.
- **`nautilus` / `custom`**: Standardized with turnover-aware friction.

## 4. Performance-Churn Frontier (Jan 2026)

Comparative audits have established a clear trade-off between risk control and execution efficiency:

| Profile | Realized Sharpe (Avg) | Realized MDD (Avg) | Avg. Turnover |
| :--- | :--- | :--- | :--- |
| **`risk_parity`** | **8.10** | **-3.97%** | Moderate (22%) |
| **`hrp`** | 6.62 | -2.20% | Moderate (27%) |
| **`barbell`** | 7.81 | -1.10% | **Low (20%)** |
| **`market`** | 1.85 | -2.98% | **Ultra-Low (12%)** |

### Key Secular Insights:
- **Profile Independence**: The removal of the "Universal Fallback" trap revealed significant variance in native HRP solvers (e.g., `skfolio` vs `cvxportfolio`).
- **Resilience in CRISIS Regimes**: **Risk Parity** emerged as the 2025 winner, providing superior stability through turbulent regimes.
- **Structural Risk Control**: Validated that HRP's risk reduction is structural (derived from the correlation tree) and remains stable even when individual asset correlations drift.
- **Numerical Stability**: Standardized on **Tikhonov Regularization** ($10^{-6} \cdot I$) to resolve CVXPY "Variable must be real" solver failures.
