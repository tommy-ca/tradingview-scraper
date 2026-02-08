# Research: Advanced Trend Regime Filters (v1)

## 1. Overview
The current `TrendRegimeFilter` relies on a simple Moving Average Crossover logic (Price > SMA200 + VWMA20 Cross). While effective as a "Circuit Breaker", it can be prone to whipsaws in sideways markets. This research explores advanced regime filters available via `pandas-ta` to improve signal quality.

## 2. Candidate Filters

### 2.1 ADX / DMI Regime
**Concept**: Use the Average Directional Index (ADX) and Directional Movement Index (DMI) to confirm trend strength and direction.
- **Indicators**: `ADX(14)`, `DMP(14)` (+DI), `DMN(14)` (-DI).
- **Logic**:
    - **Trend Existence**: `ADX > 20` (Market is trending).
    - **Trend Direction**: `+DI > -DI` (Bullish) or `-DI > +DI` (Bearish).
- **Implementation**: Available in `pandas_ta.adx()`.
- **Pros**: Explicitly measures trend strength, filtering out chop.
- **Cons**: Lagging indicator.

### 2.2 Bollinger Band Width (Squeeze)
**Concept**: Volatility regime detection. Trends often emerge from periods of low volatility (Squeeze).
- **Indicators**: `BB_WIDTH = (UPPER - LOWER) / MIDDLE`.
- **Logic**:
    - **Squeeze**: `BB_WIDTH < Threshold` (e.g., 5th percentile of history).
    - **Expansion**: `BB_WIDTH` increasing implies breakout.
- **Implementation**: `pandas_ta.bbands()`.
- **Pros**: Identifies explosive moves early.
- **Cons**: Doesn't indicate direction by itself (needs Price vs Bands).

### 2.3 Donchian Channel Breakout
**Concept**: Classic "Turtle Trading" logic.
- **Indicators**: `MAX(High, N)`, `MIN(Low, N)`.
- **Logic**:
    - **Bull**: Close > Upper Channel (20d).
    - **Bear**: Close < Lower Channel (20d).
- **Implementation**: `pandas_ta.donchian()`.
- **Pros**: Extremely robust secular trend capture.
- **Cons**: High drawdown during reversals.

### 2.4 Linear Regression Slope
**Concept**: Mathematical measurement of trend angle.
- **Indicators**: `Slope(Close, N)` or `Slope(SMA200, N)`.
- **Logic**:
    - **Bull**: `Slope > Threshold` (positive angle).
    - **Bear**: `Slope < -Threshold`.
- **Implementation**: `pandas_ta.slope()`.
- **Pros**: continuous variable, easy to threshold.
- **Cons**: Sensitive to N.

## 3. Proposed Implementation Plan

### 3.1 Feature Backfill Updates
We need to add these indicators to `backfill_features.py` to enable their use in filters.
- `adx_14`, `dmp_14`, `dmn_14`
- `bb_width`
- `donchian_upper`, `donchian_lower`
- `slope_sma200`

### 3.2 New Filter Class: `AdvancedTrendFilter`
A unified filter class supporting multiple modes:
```python
class AdvancedTrendFilter(BaseFilter):
    def __init__(self, mode="adx", params=None):
        # ...
    
    def apply(self, context):
        if mode == "adx":
            # Apply ADX > 20 & DI Cross logic
        elif mode == "donchian":
            # Apply Breakout logic
```

### 3.3 Integration
- Update `manifest.json` to allow `filters: ["advanced_trend"]`.
- Configure `adx_threshold` and `donchian_window` in profile.

## 4. Recommendation
Start with **ADX/DMI Regime** as it directly addresses the "Whipsaw" issue of simple MA crossovers by confirming *strength* before entry.
