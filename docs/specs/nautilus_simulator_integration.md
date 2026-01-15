# Specification: NautilusTrader Simulator Integration (Jan 2026)

This document defines the integration of **NautilusTrader** as a high-fidelity, event-driven backtesting backend for the TradingView Scraper framework.

## 1. Requirements

- **Parity**: NautilusTrader must produce results directionally consistent with `cvxportfolio` for the same weight sequences.
- **Event-Driven Churn**: Unlike vectorized simulators, Nautilus should model the actual execution of discrete orders.
- **Data Fidelity**: Must support daily frequency data converted from our returns matrix.
- **Metrics Integration**: Realized performance (Sharpe, MDD, Turnover) must be mapped to our standardized `calculate_performance_metrics` suite.
- **Physical Flattening**: The simulator must operate strictly on physical symbols (e.g., `BINANCE:BTCUSDT`). All logical abstractions (Strategy Atoms, Synthetic Longs) must be flattened into net physical weights *before* instantiation. The simulator is logic-agnostic.

## 2. Technical Design

### A. Data Layer
- **Component**: `NautilusDataAdapter`
- **Logic**: Convert `pd.DataFrame` returns for **physical symbols** into a list of Nautilus `Bar` objects.
- **Frequency**: Daily.

### B. Execution Layer
- **Component**: `NautilusRebalanceStrategy`
- **Logic**: 
    - On initialization: Accept **flattened** `target_weights` (Net Physical Exposure) and `initial_holdings`.
    - On first bar: Execute `MarketOrder`s to achieve target weights.
    - Post-execution: Record trade timestamps and costs.
    - **Constraint**: This component handles *execution* only. It does not perform logic inversion or synthetic mapping.

### C. Simulation Runner
- **Component**: `NautilusTraderSimulator(BaseSimulator)`
- **Workflow**:
    1. Initialize `BacktestEngine`.
    2. Register the `NautilusRebalanceStrategy`.
    3. Run the engine over the 20-day window.
    4. Extract the NAV curve from the `PortfolioAnalyzer`.

## 3. Implementation Status (Jan 2026)

- **Environment**: Successfully integrated into the native `uv` workflow. Requires **Python >=3.11, <3.13** due to `nautilus-trader` and `vectorbt` binary compatibility requirements.
- **Data Conversion**: Validated `NautilusDataAdapter` logic for converting daily returns into Nautilus `Bar` objects using `BarSpecification` and `Price(val, precision)`.
- **Simulator Status**: **Alpha (Bypass)**. The current `NautilusTraderSimulator` class is a high-fidelity wrapper that defaults to `CvxPortfolio` while the multi-asset `RebalanceStrategy` and `DataCatalog` ingestion logic are being hardened.

## 4. Q2 2026 Roadmap: Production Parity
- **Full Ingestion**: Automate the creation of temporary `ParquetDataCatalog` objects per backtest window.
- **Order Execution**: Implement the `NautilusRebalanceStrategy` to simulate the actual market impact of rebalancing orders.
- **Parity**: Establish NautilusTrader as the definitive "Production Parity" simulator, bridging the gap between backtesting and live venue execution.
