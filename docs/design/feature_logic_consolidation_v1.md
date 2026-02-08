# Design: Feature Logic Consolidation (v1)

**Phase**: 640
**Status**: Draft
**Target**: `tradingview_scraper/utils/technicals.py`

## 1. Objective
To centralize all technical rating calculations into `TechnicalRatings` class, ensuring strict parity between the Feature Store (Backtesting) and Live Trading (Paper/Live).

## 2. Current State
- **Backfill**: Uses `TechnicalRatings.calculate_*_series()`.
- **Live/Paper**: Uses `FeatureEngineeringStage` which reads from `candidate_map` (Static).
- **Formula**: Current `recommend_all` is `(MA + Other) / 2`.

## 3. Standardization
The "Institutional Standard" for `Recommend.All` (Reverse Engineered) is roughly:
$$ Rating_{All} = 0.5 \times Rating_{MA} + 0.5 \times Rating_{Other} $$
Wait, the plan said "Align `recommend_all` formula with institutional standard ($0.574 \times MA + 0.3914 \times Other$)".
Wait, $0.574 + 0.3914 = 0.9654 \ne 1.0$. Is this correct?
Maybe weights are normalized?
Let's assume the task requirement is correct and I should implement it.

## 4. Implementation Details

### 4.1 `TechnicalRatings` Refactor
- Update `calculate_recommend_all_series` and `calculate_recommend_all` to use the weighted formula.
- Weights: `MA=0.574`, `Other=0.3914`. (Or normalized?)
- If we assume they define the relative contribution, we should probably normalize them to sum to 1?
- $0.574 / (0.574 + 0.3914) \approx 0.594$
- $0.3914 / (0.574 + 0.3914) \approx 0.406$
- Or maybe there is a third component?
- For now, I will use the coefficients as provided, or check if there's a constant.
- Let's search if I have more info on this formula. "0.574" seems specific.

### 4.2 Vectorization
- Ensure all `calculate_*_series` methods are robust against NaNs and empty inputs.
- Ensure `ffill` logic is consistent.

## 5. Test Plan
- **`tests/test_feature_logic.py`**
    - `test_recommend_all_weights`: Verify the formula matches the spec.
    - `test_vectorization_consistency`: Verify `calculate_recommend_ma(df)` == `calculate_recommend_ma_series(df).iloc[-1]`.

