# Design Document: Nautilus Parity Integration (v1)

## 1. Objective
Ensure bit-perfect parity between research backtests and live execution by using **NautilusTrader** as the unified event-driven engine. This replaces the legacy `ReturnsSimulator` bypass with a high-fidelity simulation that respects exchange limits.

## 2. Architecture

### 2.1 Metadata Bridge: `NautilusInstrumentProvider`
Nautilus requires strict `Instrument` definitions. This component will:
- Query `data/lakehouse/execution.parquet` (managed by `ExecutionMetadataCatalog`).
- Map unified symbols (e.g., `BINANCE:BTCUSDT`) to Nautilus `InstrumentId`.
- Set `price_precision` and `size_precision` based on `tick_size` and `step_size`.

### 2.2 Data Bridge: `NautilusDataConverter`
- Convert `portfolio_returns.pkl` (daily returns) into Nautilus `Bar` objects.
- Generate a temporary `ParquetDataCatalog` per backtest window.
- Ensure timestamps are aligned with the `market-day` (+4h shift) normalization.

### 2.3 Strategy: `NautilusRebalanceStrategy`
This is the core execution logic:
- **Input**: A time-indexed DataFrame of target weights.
- **On Bar**: 
    1. Calculate `target_qty = (PortfolioValue * TargetWeight) / CurrentPrice`.
    2. **Precision Guard**: Round down to `lot_size` / `step_size`.
    3. **Minimum Gate**: Skip if `target_qty * CurrentPrice < min_notional`.
    4. **Execution**: Submit `MarketOrder`.

### 2.4 Backtest Runner: `NautilusSimulator`
- Wraps the Nautilus `BacktestEngine`.
- Maps standard backtest inputs (`returns`, `weights_df`, `initial_holdings`) to Nautilus components.
- Post-run: Extract the NAV curve and trade history to calculate standard metrics (Sharpe, MDD, Turnover).

## 3. Parity Requirements [MET]
- **Friction**: Nautilus transaction costs must be calibrated to match `backtest_slippage` and `backtest_commission`.
- **Divergence Gate**: Annualized return divergence between `cvxportfolio` and `nautilus` must be **< 1.5%**.
- **Observability**: The `NautilusRebalanceStrategy` must log daily NAV snapshots. Silent failures in NAV calculation (resulting in flat 0% return curves) are treated as critical integration bugs.
- **State Integrity**: The `_get_nav()` method must robustly handle `InstrumentId` string conversions between the unified venue format (`AVGO.BACKTEST`) and internal tracking keys.

## 4. Live Bridge (L6)
Once parity is proven in backtest, the same `NautilusRebalanceStrategy` will be deployed to a live `NautilusTrader` node using:
- `BinanceLiveExecutionClient` (Crypto)
- `IbLiveExecutionClient` (IBKR)

## 5. Audit & Troubleshooting
- **Engine Health Check**: Use `tests/test_nautilus_parity.py` to verify that the simulator produces non-zero returns on synthetic data.
- **Common Failures**:
    - **Flat Returns (0.00%)**: Indicates a failure in `_get_nav()` to retrieve cash or positions. Check logs for "Failed to get cash balance".
    - **High Divergence**: Indicates a mismatch in friction settings (`backtest_slippage`) or timestamp alignment between the vectorized and event-driven engines.
