# Design: Multi-Timeframe Trend Strategy (v1)

## 1. Overview
The **MTF Trend Strategy** implements a classic "Golden Cross" logic enhanced with Multi-Timeframe (MTF) regime confirmation. It operates on the "Broad Scan, Deep Filter" principle to ensure robust signal generation.

## 2. Architecture

### 2.1 The "Broad Scan" (Discovery)
- **Scanner**: `binance_spot_liquidity`
- **Logic**:
    - Volume > $10M
    - Volatility > 1%
    - No technical filters (pure universe selection).
- **Goal**: Recruit all liquid assets to the Lakehouse.

### 2.2 The "Deep Filter" (Alpha Selection)
- **Component**: `TrendRegimeFilter` (Pillar 1)
- **Inputs**:
    - `close` (Daily)
    - `sma_200` (Trend Baseline)
    - `vwma_20` (Signal Line)
- **Logic (Long)**:
    1.  **Regime Check**: `Close > SMA_200`. (Asset is in a secular uptrend).
    2.  **Signal Check**: `VWMA_20` crosses *above* `SMA_200`.
    3.  **Recency Check**: Crossover occurred within the last `lookback_window` (default 5 bars).
- **Logic (Short)**:
    1.  **Regime Check**: `Close < SMA_200`.
    2.  **Signal Check**: `VWMA_20` crosses *below* `SMA_200`.

### 2.3 The "Fractal Sleeve" (Optimization)
- **Sleeve A**: `binance_spot_trend_long` (Captures Bull Trends).
- **Sleeve B**: `binance_spot_trend_short` (Captures Bear Trends).
- **Meta-Portfolio**: Allocates between Trend, Mean Reversion, and Cash.

## 3. Implementation Details

### 3.1 Feature Backfill (DataOps)
The `backfill_features.py` service must compute:
-   `sma_200`: Simple Moving Average (200d).
-   `vwma_20`: Volume-Weighted Moving Average (20d).
    - Formula: `sum(close * volume, window) / sum(volume, window)`

### 3.2 Filter Logic (`TrendRegimeFilter`)
```python
def apply(self, context):
    # Load history from Lakehouse
    for symbol in candidates:
        hist = context.history[symbol]
        
        # 1. Regime (Smoothed with Hysteresis)
        # Allows using VWMA or SMA50 as price proxy to reduce noise
        current_proxy = hist[self.regime_source][-1]
        current_base = hist['sma_200'][-1]
        
        # Bull if Proxy > SMA * (1 + threshold)
        is_bull = current_proxy > (current_base * (1.0 + self.threshold))
        
        # 2. Crossover
        # Check last N days for crossover event
        cross_detected = False
        for i in range(1, window+1):
            prev_diff = hist['vwma_20'][-(i+1)] - hist['sma_200'][-(i+1)]
            curr_diff = hist['vwma_20'][-i] - hist['sma_200'][-i]
            
            if prev_diff < 0 and curr_diff > 0: # Golden Cross
                cross_detected = True
                break
        
        if not (is_bull and cross_detected):
            veto(symbol)
```

## 4. Workflow Integration
1.  **Scanner**: Run `binance_spot_liquidity`.
2.  **DataOps**: Ingest and Calculate `SMA/VWMA`.
3.  **Alpha**: Run `trend_long` and `trend_short` sleeves.
4.  **Meta**: Combine with existing `rating_all` sleeves for diversification.
