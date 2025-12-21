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

### Stage 3: Portfolio Construction (MPT)
*   **Tool**: `scripts/optimize_portfolio.py` (Modern Portfolio Theory)
*   **Theory**:
    *   **Minimum Variance**: Solves for weights that minimize total portfolio volatility.
    *   **Risk Parity**: Allocates such that each asset contributes an equal amount of risk.
*   **Synthetic Longs**: Short signals are return-inverted to allow the optimizer to treat them as positive contributors to the hedged portfolio.

### Stage 4: Metadata Cataloging & PIT
*   **Tool**: `tradingview_scraper.symbols.stream.metadata`
*   **Persistence**: `data/lakehouse/symbols.parquet`
*   **Goal**: Ensure all portfolio constituents have verified tick sizes, timezones, and Point-in-Time (PIT) history to prevent look-ahead bias during backtests.

## 3. Automation Commands
```bash
# 1. Run Scanners
bash scripts/run_crypto_scans.sh
bash scripts/run_local_scans.sh

# 2. Prepare Returns Matrix
PYTHONPATH=. python3 scripts/prepare_portfolio_data.py

# 3. Optimize Weights
PYTHONPATH=. python3 scripts/optimize_portfolio.py
```
