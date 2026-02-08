# Design: Scanner Simplification (v1)

## 1. Problem Statement
The current Scanner architecture (`FuturesUniverseSelector`) mixes **Universe Selection** (Liquidity/Volatility) with **Strategy Logic** (Trend/MTF filters).
*   **Opacity**: "Trend" logic is hidden inside scanner configs (`trend: { direction: long }`) and executed against TradingView's black-box data.
*   **Duplication**: We implemented robust Python filters (`TrendRegimeFilter`, `AdvancedTrendFilter`) but the scanner still tries to pre-filter assets.
*   **Scarcity**: Strict scanner filters (e.g. "SMA200") often return 0 candidates in bear markets, killing the pipeline before Python logic can run.

## 2. The Solution: "Dumb & Liquid" Scanners
We will decouple **Discovery** from **Strategy**.
*   **Scanners**: Responsible ONLY for Liquidity, Volatility, and Market Cap.
    *   Goal: "Get me the top 100 liquid assets."
*   **Pipeline**: Responsible for Regime, Trend, Signal, and Vetoes.
    *   Goal: "Filter these 100 assets for the ones matching my strategy."

## 3. Implementation Plan

### 3.1 Config Refactoring
All `binance_spot_trend_*` and `rating_*` scanner configs will be updated to inherit from a **Base Liquidity Profile** and REMOVE the `trend:` block.

**Base Config (`binance_spot_liquidity.yaml`)**:
```yaml
volume: { min: 1000000 }
volatility: { min: 0.5 }
limit: 200
sort_by: volume
```

**Strategy Config (`binance_spot_trend_long.yaml`)**:
*   Old: `trend: { direction: long }`
*   New: `metadata: { intent: "LONG" }` (Only for tagging, not filtering).

### 3.2 Code Update (`FuturesUniverseSelector`)
*   Deprecate/Remove `_evaluate_trend` method.
*   Ensure `intent_direction` can be passed via `metadata` block in config, not just `trend` block.

### 3.3 Pipeline Update (`PolicyStage`)
*   The `TrendRegimeFilter` (Pillar 1) becomes the **Sole Authority** on trend.
*   This ensures we have full visibility (logs) on why an asset failed (e.g., "Close 0.5 < SMA 0.6") rather than it just "not appearing" in the scan.

## 4. Benefit
*   ** observability**: We see 100 candidates entering the funnel and 5 surviving.
*   **Flexibility**: We can change trend logic (SMA -> EMA -> Donchian) in Python without touching scanner configs.
*   **Robustness**: Scanners won't fail empty just because the market is bearish.
