# Specification: Backtest Engine V2 (Multi-Simulator Framework)

This document defines the architecture for the institutional backtesting framework, enabling comparative validation between idealized returns-based simulation and high-fidelity market simulation.

## 1. Overview

The framework decouples **Window Management** (rolling walk-forward logic) from **Market Simulation** (execution logic). This allows us to benchmark the impact of transaction costs, slippage, and liquidity on our optimization engines.

## 2. Simulation Backends

### 2.1 Returns Simulator (Internal Baseline)
- **Method**: Direct dot-product of weights and daily returns.
- **Daily Rebalancing**: Models daily rebalancing to target weights, ensuring mathematical parity with policy-based simulators.
- **Use Case**: Rapid alpha validation and idealized benchmarking.

### 2.2 CVXPortfolio Simulator (Convex Policy)
- **Method**: Utilizes `cvxportfolio.MarketSimulator`.
- **Friction Models**:
    - **Slippage**: Default 5 bps (0.0005) per trade.
    - **Commission**: Default 1 bp (0.0001) per trade.
    - **Market Impact**: Volume-based quadratic impact (requires OHLCV data).
- **Cash Management**: Uses a stablecoin (USDT) as the base currency for the simulator's cash account.
- **Use Case**: Institutional implementation audit and "Slippage Decay" analysis.

### 2.3 VectorBT Simulator (High-Performance Vectorized)
- **Method**: Utilizes `vectorbt.Portfolio.from_returns`.
- **Friction Models**:
    - **Slippage**: Default 5 bps per trade.
    - **Fees**: Default 1 bp commission.
- **Processing**: Numba-accelerated vectorized operations.
- **Use Case**: Fast event-driven simulation and large-scale parameter sweeps.

## 3. Metrics & Standards

Every simulator must output a standardized result schema, utilizing **QuantStats** for mathematical consistency:
- **Returns**: Geometric cumulative return and annualized mean.
- **Risk**: Annualized Volatility, Max Drawdown, and CVaR (95%).
- **Efficiency**: Sharpe Ratio, **Sortino Ratio**, **Calmar Ratio**, and Win Rate.
- **Operations**: 1-way Turnover ($ \sum |w_{t} - w_{t-1}| / 2 $).

All backends are forced through the unified `calculate_performance_metrics` utility to ensure zero mathematical drift between simulators.

## 4. Dynamic Universe Rebalancing

The framework supports **Adaptive Selection** at each rebalancing step, enabling the portfolio to evolve as market regimes shift.
- **Dynamic Pruning**: Re-runs the "Natural Selection" phase at the start of every walk-forward window using only the trailing history available at that point in time (Point-in-Time safety).
- **Identity Evolution**: Allows the portfolio to rotate out of stale assets and into new market leaders as correlations and momentum diverge within clusters.
- **Transition Costs**: Simulators (especially `CvxPortfolioSimulator`) correctly model the friction of closing old positions and opening new ones during these universe shifts.
- **Implementation**: Managed in `BacktestEngine.run_tournament` by calling `run_selection` from `scripts.natural_selection` at each iteration.

## 5. High-Fidelity Simulations

To ensure backtest results mirror real-world implementation, the framework employs several advanced modeling techniques:

### 5.1 Point-in-Time (PIT) Risk Auditing
The backtester no longer uses static risk scores. At each window start, it executes the production `AntifragilityAuditor` on the training returns. This ensures that the optimizer reacts to historical tail-risk events (e.g., flash crashes) just as it would in live production.

### 5.2 State Persistence (Cross-Window Transitions)
Simulators maintain position state between walk-forward windows.
- **Friction Continuity**: When moving from Window N to Window N+1, the simulator calculates transaction costs for the delta between the *realized ending weights* of the previous window and the *target weights* of the new window.
- **Cash Management**: Residual cash and dividends are preserved across the simulation timeline.

### 5.3 Multi-Engine Benchmarking (The Tournament)
The `Tournament` mode runs a 3D matrix of (Profile x Engine x Simulator). This allows us to identify "Alpha Decay"—the difference between idealized mathematical returns and realized returns after friction and data gaps.

### 5.4 Initial Holdings & Warm Starts
To eliminate the "First-Trade Bias" (where starting from 100% cash creates an artificial spike in turnover and transaction costs), the engine supports **Warm-Start Initialization**.
- **Mechanism**: The backtester attempts to load the last implemented state from `data/lakehouse/portfolio_actual_state.json`.
- **Initialization**: If found, the weights of the *first* walk-forward window are compared against these actual holdings. Transaction costs are only calculated for the delta.
- **Fallback**: If no state file exists, the simulation assumes a start from 100% Cash (Institutional Conservative bias).

## 12. Rebalance Fidelity (Drift vs. Reset)

The framework supports two rebalancing modes controlled by the `feat_rebalance_mode` flag:

### 12.1 Daily Reset (`daily`)
The portfolio is mathematically reset to the target weights at the end of every trading day. This is the legacy research mode used for purely statistical risk-parity studies. It ignores the "Drift Risk" that occurs when assets diverge within a rebalance period.

### 12.2 Window Drift (`window`)
Target weights are established only on the first day of the walk-forward window. Assets are allowed to drift based on their realized price returns for the remainder of the period (e.g., 20 days). This provides a high-fidelity validation of the actual implementation slippage.

## 13. Directional Integrity (Scanner-Locked)

To maintain strategy-locked alpha, the backtester enforces **Scanner-Locked Directions**:
- **Long-Only Scanners**: Assets discovered via long-only technical filters are strictly constrained to positive weights ($w \ge 0$).
- **Short-Only Scanners**: Assets discovered via short-only technical filters are strictly constrained to negative weights ($w \le 0$).
- **Borrow Costs**: Simulators apply an annualized borrow fee (default 2% p.a., gated by `feat_short_costs`) to all short positions to reflect institutional financing friction.

## 6. Institutional Standards (2025 Standard)
...


| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Lookback** | 500 Days | Historical depth for discovery and secular validation. |
| **Train Window** | 252 Days | Full trading year history for optimization history buffer. |
| **Test Window** | 20 Days | Rolling validation window. |
| **Threshold** | 0.55 | Tighter clustering distance for high-conviction groups. |
| **Top N** | 1 | Focus capital on the single lead alpha asset per cluster. |
| **Baseline** | `AMEX:SPY` | Primary benchmark for all multi-asset comparisons. |
| **Friction** | 5bps Slippage / 1bp Commission | Real-world execution modeling. |

## 7. Multi-Calendar Correlation Logic

The framework supports mixed calendars (24/7 Crypto + 5/7 TradFi).
- **Portfolio Returns**: Preserve all trading days (sat/sun included for crypto).
- **Benchmark Alignment**: TradFi benchmarks (`SPY`) are mapped to the portfolio calendar. Benchmark returns on weekends are treated as `0.0`, ensuring that weekend crypto alpha is captured without benchmark bias.
- **No Padding**: The returns matrix no longer zero-fills non-trading days for TradFi assets, preserving statistical variance and Sharpe accuracy.

## 8. Tournament Matrix (3D Benchmarking)

The "Tournament" evaluates a 3D matrix of `[Simulator] x [Engine] x [Profile]`.

### 8.1 Dimensions
- **Simulators**: `ReturnsSimulator` (Idealized), `CvxPortfolioSimulator` (Convex Policy), `VectorBTSimulator` (Vectorized Event-Driven).
- **Engines**: `Custom (Cvxpy)`, `skfolio`, `Riskfolio-Lib`, `PyPortfolioOpt`, `CvxPortfolio`, **`Market`**.
- **Profiles**: `MinVar`, `HRP`, `MaxSharpe`, `Antifragile Barbell`, `BuyHold`.

### 8.2 Hierarchical Risk Parity (HRP) Standards
The HRP profile aims for equal risk contribution across hierarchical clusters.
- **Custom Engine**: Implements a **Convex Risk Parity** approximation using a log-barrier objective on cluster benchmarks.
- **Linkage**: The standard production linkage is **Ward** on **Intersection Correlation**.

## 9. Market Baseline Engine
The framework treats the market benchmark as a first-class **"Market" Engine**.
- **Strategy**: 100% Long `baseline_symbol` (default: `AMEX:SPY`).
- **Standardized**: Appears in the 3D Tournament matrix alongside optimization engines.
- **Zero-Bias**: Sourced directly from raw lakehouse data, bypassing scanner-specific direction flipping.

## 10. Unified QuantStats Reporting
The reporting pipeline is rebased entirely on **QuantStats** to ensure mathematical consistency.
- **Slippage Decay Audit**: Generates a detailed comparison between idealized and realized returns to quantify implementation friction (Gated by `feat_decay_audit`).

## 11. Alpha Isolation (Selection vs. Optimization)

The framework isolates alpha sources by comparing three distinct tiers:
1. **Raw Pool EW**: Equal-weighted basket of all candidates found during discovery.
2. **Filtered EW**: Equal-weighted basket of the Top N assets per cluster selected by the `NaturalSelection` logic.
3. **Optimized Weights**: Cluster-weighted allocation produced by the optimization engine (e.g., MinVar, HRP).

- **Selection Alpha**: Measured as the spread between Tier 2 and Tier 1. This quantifies the value of the pruning logic.
- **Optimization Alpha**: Measured as the spread between Tier 3 and Tier 2. This quantifies the value of the statistical weighting engine.
