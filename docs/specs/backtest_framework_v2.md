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

## 5. Alpha Momentum Gates

To prevent forced allocation into "best of the losers" clusters:
- **Momentum Gate**: Assets with negative cumulative returns over the selection lookback are disqualified.
- **Adaptive Weighting**: If an entire cluster fails the momentum gate, its weight is assigned to the **Cash Asset (USDT)**.
- **Purpose**: Ensures the portfolio maintains a positive-expectancy bias even in variance-minimizing profiles.

## 6. Institutional Standards (2025 Standard)

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
