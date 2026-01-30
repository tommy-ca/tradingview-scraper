---
status: pending
priority: p1
issue_id: 001
tags: ['performance', 'critical', 'backfill']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `scripts/services/backfill_features.py` script contains a critical performance bug where technical ratings are computed twice for every symbol. The method `calculate_recommend_all_series` internally calls the individual MA and Oscillator calculations, but the script also calls these individually beforehand. This effectively doubles the CPU load for the most expensive part of the pipeline.

## Findings
- **File**: `scripts/services/backfill_features.py`
- **Lines**: 109-111
- **Evidence**:
  ```python
  ma = TechnicalRatings.calculate_recommend_ma_series(df)      # Calc 1
  osc = TechnicalRatings.calculate_recommend_other_series(df)  # Calc 2
  rating = TechnicalRatings.calculate_recommend_all_series(df) # Calc 3 (Triggers 1 & 2 internally)
  ```
- **Risk**: Backfill jobs for large universes (crypto + stocks) will take 2x longer than necessary, wasting compute credits and delaying data availability.

## Proposed Solutions

### Solution A: Arithmetic Mean (Recommended)
Since we already calculate `ma` and `osc` explicitly, simply compute the `rating` as the average of the two.
```python
rating = (ma + osc) / 2.0
```
This is mathematically identical to what `calculate_recommend_all_series` does but executes instantly as a vectorized operation.

### Solution B: Drop Individual Calls
If the individual components `ma` and `osc` are not needed for storage, remove lines 109-110. (However, we usually store these components for ML features, so Solution A is preferred).

## Technical Details
- Edit `scripts/services/backfill_features.py`.
- Replace the expensive function call with the arithmetic operation.

## Acceptance Criteria
- [ ] `backfill_features.py` no longer calls `calculate_recommend_all_series`.
- [ ] `rating` column is populated with `(ma + osc) / 2`.
- [ ] Unit tests confirm the values match the previous implementation.

## Work Log
- 2026-01-29: Issue identified by Performance Oracle.
