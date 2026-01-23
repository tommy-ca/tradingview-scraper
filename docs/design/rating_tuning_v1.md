# Design: Rating Logic Tuning (v1)

## 1. Objective
To achieve numerical parity (MAE < 0.05) between the replicated technical ratings (`TechnicalRatings`) and the ground truth from TradingView, specifically addressing the divergence in `Recommend.MA`.

## 2. Tuning Targets

### 2.1 Ichimoku Cloud Alignment
- **Hypothesis**: The divergence in `Recommend.MA` is likely due to incorrect Ichimoku Cloud displacement handling.
- **Current Logic**: `span_a = ichimoku_df["ISA_9"]`, `span_b = ichimoku_df["ISB_26"]` (no shift).
- **TradingView Logic**:
  - The Cloud (Kumo) is plotted 26 bars into the future.
  - The "Current Cloud" value used for rating is the value of Span A/B calculated 26 bars ago.
  - **Proposed Fix**: Revert to `shift(26)` logic but verify `pandas-ta` alignment.

### 2.2 EMA vs SMA Weighting
- **Hypothesis**: TradingView might weight exponential averages differently than simple averages.
- **Current Logic**: Equal weight for all MAs.
- **Experiment**: Check if giving higher weight to EMA reduces error.

### 2.3 Smoothing Variations
- **Hypothesis**: RSI and Stochastic smoothing might differ (Wilder vs EMA).
- **Current Logic**: `ta.rsi` uses standard RMA/Wilder.
- **Experiment**: Verify `pandas-ta` default matches TV.

## 3. Iterative Tuning Process
1.  **Baseline**: Run `audit_feature_parity.py` to get current MAE.
2.  **Experiment**: Modify `TechnicalRatings` logic (one indicator at a time).
3.  **Validate**: Re-run audit script.
4.  **Repeat**: Until MAE < 0.05.

## 4. TDD Strategy
- **`tests/test_rating_tuning.py`**:
    - Focus on specific indicator alignment (e.g., `test_ichimoku_displacement`).
    - Use manually verified "micro-ground-truth" points.
