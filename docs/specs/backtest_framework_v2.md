# Specification: Backtest Engine V2 (Multi-Simulator Framework)

This document defines the architecture for the institutional backtesting framework, enabling comparative validation between idealized returns-based simulation and high-fidelity market simulation.

## 1. Overview

The framework decouples **Window Management** (rolling walk-forward logic) from **Market Simulation** (execution logic). This allows us to benchmark the impact of transaction costs, slippage, and liquidity on our optimization engines.

## 2. Simulation Backends

### 2.1 Returns Simulator (Internal Baseline)
- **Method**: Direct dot-product of weights and daily returns.
- **Assumptions**: Zero friction, perfect liquidity, instantaneous rebalancing.
- **Use Case**: Rapid alpha validation and idealized benchmarking.

### 2.2 CVXPortfolio Simulator (High-Fidelity)
- **Method**: Utilizes `cvxportfolio.MarketSimulator`.
- **Friction Models**:
    - **Slippage**: Default 5 bps (0.0005) per trade.
    - **Commission**: Default 1 bp (0.0001) per trade.
    - **Market Impact**: Volume-based quadratic impact (requires OHLCV data).
- **Cash Management**: Uses a stablecoin (USDT) as the base currency for the simulator's cash account.
- **Use Case**: Institutional implementation audit and "Slippage Decay" analysis.

## 3. Metrics & Standards

Every simulator must output a standardized result schema, utilizing **QuantStats** for mathematical consistency:
- **Returns**: Geometric cumulative return and annualized mean.
- **Risk**: Annualized Volatility, Max Drawdown, and CVaR (95%).
- **Efficiency**: Sharpe Ratio, **Sortino Ratio**, **Calmar Ratio**, and Win Rate.
- **Operations**: 1-way Turnover ($ \sum |w_{t} - w_{t-1}| / 2 $).

## 4. Visual Tear-sheets

The framework automatically generates HTML tear-sheets using `quantstats.reports.html()` for all tournament benchmark points.
- **Location**: `artifacts/summaries/runs/<RUN_ID>/tearsheets/`
- **Benchmark**: `AMEX:SPY` is used as the default relative performance reference.

## 4. Institutional Constants

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `Slippage` | 0.0005 (5 bps) | Linear execution cost. |
| `Commission` | 0.0001 (1 bp) | Trading fee per unit. |
| `Cash Asset` | `USDT` | Reference asset for simulation liquidity. |
| `Train Window` | 120 Days | History for optimization. |
| `Test Window` | 20 Days | Walk-forward validation period. |

## 5. Tournament Matrix (3D Benchmarking)

The "Tournament" now evaluates a 3D matrix of `[Simulator] x [Engine] x [Profile]`.

### 5.1 Dimensions
- **Simulators**: `ReturnsSimulator` (Idealized), `CvxPortfolioSimulator` (Realized).
- **Engines**: `Custom (Cvxpy)`, `skfolio`, `Riskfolio-Lib`, `PyPortfolioOpt`, `CvxPortfolio`.
- **Profiles**: `MinVar`, `HRP`, `MaxSharpe`, `Antifragile Barbell`.

### 5.2 Performance Optimization: Weight Caching
To minimize compute overhead, the framework implements **Weight Caching**. For each window:
1.  All enabled **Engines** generate weights for each **Profile**.
2.  The resulting weights are cached in-memory.
3.  All enabled **Simulators** consume the cached weights to compute realized performance.
    - *Result*: Optimization happens once ($N_{eng} \times N_{prof}$), Simulation happens $N_{sim}$ times.

### 5.3 Alpha Decay Audit
The report includes an "Alpha Decay" table per profile, calculating the delta between Idealized Sharpe (zero friction) and Realized Sharpe (with slippage/commission).
