# Design Specification: Dynamic Historical Backtesting & Synthetic Backfill (v1.0)

## 1. Objective
Enable the platform to perform high-fidelity backtesting of Rating-based strategies by reconstructing historical technical features (`Recommend.All`, `Recommend.MA`, etc.) from raw OHLCV data. This resolves the "Discovery-Backtest Regime Mismatch" where scanners currently only provide current-time signals.

## 2. Architecture

### 2.1 The Historical Feature Store
A new artifact, `features_matrix.parquet`, will be generated alongside `returns_matrix.parquet`.
- **Index**: DateTime (UTC).
- **Columns**: Multi-Index `[Symbol, Feature]`.
- **Storage**: Run-specific data directory (`artifacts/summaries/runs/<RUN_ID>/data/`).

### 2.2 Synthetic Backfill Service (`HistoricalFeatureBackfill`)
A service that leverages `tradingview_scraper.utils.technicals.TechnicalRatings` to generate time-series signals for all assets in a universe.
- **Logic**: For each date $T$ in the backtest lookback, calculate the 15-component MA and 11-component Oscillator ratings.
- **Optimization**: The calculation is vectorized or batched per asset to minimize `pandas-ta` overhead.

### 2.3 Dynamic Backtest Integration
The `BacktestEngine` will be updated to:
1. Load the `features_matrix.parquet`.
2. At each rebalance window $T$:
   - Retrieve the cross-sectional slice of features for all active symbols.
   - Re-rank and Re-select the portfolio candidates using the **Historical Signal** instead of the current-time scanner signal.
   - Hand off the selected subset to the optimization solvers.

## 3. Implementation Plan

### Step 1: Feature Backfill Service (`scripts/services/backfill_features.py`)
- Create a script that takes `portfolio_candidates.json` and `returns_matrix.parquet`.
- Iterates over symbols and computes full-history ratings.
- Consolidates into a wide-format Parquet.

### Step 2: Backtest Engine Refactoring (`scripts/backtest_engine.py`)
- Add support for `historical_features` parameter.
- Implement re-selection logic inside the window loop.
- Ensure compatibility with existing `NaturalSelection` policy stages.

### Step 3: Pipeline Integration
- Add `Feature Backfill` as a standard step in the Alpha Cycle.
- Update `scripts/run_production_pipeline.py` to orchestrate the backfill before validation.

## 4. Success Criteria
- `features_matrix.parquet` exists and contains valid ratings for all symbols.
- Backtest rebalances show dynamic symbol rotation based on historical rating changes.
- Forensic audit confirms zero lookahead bias.
