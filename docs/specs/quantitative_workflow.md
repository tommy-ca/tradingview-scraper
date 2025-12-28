# Specification: Quantitative Workflow Pipeline
**Status**: Formalized
**Date**: 2025-12-21

## 1. Overview
This document defines the standardized pipeline for transforming raw market data into an optimized, multi-asset portfolio.

## 2. Pipeline Stages

### Stage 1: Base Universe Selection
*   **Tool**: `tradingview_scraper.futures_universe_selector`
*   **Input**: `configs/crypto_cex_base_*.yaml`
*   **Process**: Filters thousands of raw instruments by liquidity floor (Value Traded), market cap rank, and exchange priority.
*   **Output**: High-liquidity "Base Universes" per exchange/market.

### Stage 2: Strategy Filtering (Signal Generation)
*   **Process**: Applies technical strategy rules (Trend Momentum, Mean Reversion) to the Base Universe.
*   **Parameters**: ADX thresholds, RSI levels, Performance horizons (1W, 1M, 3M).
*   *Note*: Short signals are identified for trend-reversal or defensive positioning.

### Stage 3: Natural Selection (Pruning)
*   **Tool**: `scripts/natural_selection.py`
*   **Process**: Performs hierarchical clustering on Pass 1 (60d) data. Selects the Top N assets per cluster based on **Execution Intelligence** (Liquidity + Momentum + Convexity).
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

## 3. Automation Commands
```bash
# Full end-to-end run
make clean-run

# Or step-by-step (tiered selection + analysis + finalize)
make scans
make prep-raw
make prune TOP_N=3 THRESHOLD=0.4
make align LOOKBACK=200
make analyze
make finalize
```
