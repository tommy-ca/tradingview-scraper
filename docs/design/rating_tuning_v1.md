# Design: Rating Logic Tuning (v1)

**Phase**: 660
**Status**: Active
**Target**: `tradingview_scraper/utils/technicals.py`

## 1. Objective
To refine the `Recommend.MA` calculation logic to match TradingView's proprietary methodology, specifically regarding the Ichimoku Cloud component.

## 2. Research Findings
- **TradingView Logic**: For the "Moving Averages" rating, the Ichimoku component is based on **Price vs Base Line (Kijun-sen)**, NOT Price vs Cloud (Span A/B).
- **Current Implementation**: Compares `Close` vs `Max(SpanA, SpanB)` (Cloud Top/Bottom).
- **Parity Gap**: This causes divergence when Price is above Base Line but inside/below Cloud (or vice versa).

## 3. Specification

### 3.1 Ichimoku Component
- **Inputs**: High, Low, Close.
- **Parameters**: 
    - Base Line Length (Kijun): 26
    - Displacement: 26 (Standard, but Kijun itself is not shifted for the comparison in many implementations. We need to verify if TV compares Price(t) vs Kijun(t) or Kijun(t-26)).
    - *Hypothesis*: TV uses current Kijun.
    - Formula: $Kijun = (HighestHigh(26) + LowestLow(26)) / 2$
- **Logic**:
    - Buy: $Close > Kijun$
    - Sell: $Close < Kijun$
    - Neutral: $Close == Kijun$

### 3.2 Impact
- This simplifies the calculation (no need to compute Spans or handle forward shift).
- Should improve correlation with `Recommend.MA`.

## 4. Implementation Plan
1.  Update `TechnicalRatings.calculate_recommend_ma_series`.
2.  Replace the Cloud comparison block with Kijun comparison.
3.  Use `pandas_ta.donchian` or direct calculation for Kijun if `ichimoku` function is too heavy/complex.
    - `pandas_ta.ichimoku` returns Kijun as `IKS_26`.

## 5. Test Plan
- **`tests/test_rating_tuning.py`**
    - `test_ichimoku_logic`: Create synthetic data where Price > Kijun but Price < Cloud. Verify vote is +1 (Buy).
