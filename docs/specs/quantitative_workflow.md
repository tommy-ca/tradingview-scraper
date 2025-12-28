# Specification: Quantitative Workflow Pipeline
**Status**: Formalized
**Date**: 2025-12-21

## 1. Overview
This document defines the standardized pipeline for transforming raw market data into an optimized, multi-asset portfolio.

## 2. Pipeline Stages

### Stage 1: Discovery & Scans
*   **Tools**: `tradingview_scraper.futures_universe_selector`, `tradingview_scraper.cfd_universe_selector`, `tradingview_scraper.bond_universe_selector`
*   **Entry point**: `make scans` (local + crypto scans, plus bonds + Forex MTF)
*   **Input**: `configs/*.yaml` strategy configs (trend, mean reversion, MTF)
*   **Output**: `export/universe_selector_*.json` scan results with LONG/SHORT tags
*   **US equities note**: Avoid the TradingView screener field `index` (can return HTTP 400 "Unknown field"); constrain with `include_symbol_files` (e.g. `data/index/sp500_symbols.txt`).

### Stage 2: Strategy Filtering (Signal Generation)
*   **Process**: Applies technical strategy rules (Trend Momentum, Mean Reversion) to the Base Universe.
*   **Parameters**: ADX thresholds, RSI levels, Performance horizons (1W, 1M, 3M).
*   *Note*: Short signals are identified for trend-reversal or defensive positioning.

### Stage 3: Natural Selection (Pruning)
*   **Tool**: `scripts/natural_selection.py`
*   **Process**: Performs hierarchical clustering on Pass 1 (60d) data. Selects the Top N assets per cluster based on **Execution Intelligence** (Liquidity + Momentum + Convexity).
*   **Health gate**: `make prune` runs `scripts/validate_portfolio_artifacts.py --mode raw --only-health` after the Pass 1 backfill; this is the first hard stop for STALE/MISSING assets.
*   **Identity Merging**: Canonical venue merging happens here to avoid redundant exchange risk (e.g., BTC across 5 exchanges).

### Stage 4: Risk Optimization (Clustered V2)
*   **Tool**: `scripts/optimize_clustered_v2.py`
*   **Process**: Optimizes weights across clusters using hierarchical risk buckets. Supports **Min Variance, Risk Parity, Max Sharpe, and Barbell** profiles.
*   **Insulation**: Strictly enforced 25% systemic cap per cluster.

### Stage 5: Validation & Backtesting
*   **Tool**: `scripts/backtest_engine.py`
*   **Process**: 13th Step of the production lifecycle. Performs a Walk-Forward validation to verify realized volatility and returns against the optimizer's goals.
*   **Target Achievement**: Automatically audits if `MIN_VARIANCE` actually delivered lower volatility than other profiles during the test period.

### Stage 6: Implementation & Reporting
*   **Output**: Implementation Dashboard (`make display`), Strategy Resume (`summaries/backtest_comparison.md`), and Audit Log (`summaries/selection_audit.md`).
*   **Publishing**: `make gist` syncs `summaries/` to a private GitHub Gist (skips sync if `summaries/` is empty unless `GIST_ALLOW_EMPTY=1`).

## 3. Automation Commands
```bash
# Daily incremental run (recommended; preserves cache/state; includes gist preflight)
make daily-run

# Full reset run (blank slate)
make clean-run

# After implementing new target weights
make accept-state

# Or step-by-step (tiered selection + analysis + finalize)
make scans
make prep-raw  # best-effort raw health check (may be stale before backfill)
make prune TOP_N=3 THRESHOLD=0.4
make align LOOKBACK=200
make analyze
make finalize
```
