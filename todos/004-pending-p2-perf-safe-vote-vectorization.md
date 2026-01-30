---
status: pending
priority: p2
issue_id: 004
tags: ['performance', 'optimization']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `_safe_vote` method in `tradingview_scraper/utils/technicals.py` uses inefficient Pandas `reindex` and `loc` assignment operations inside a high-frequency loop (called 30+ times per symbol). This creates unnecessary memory allocation overhead.

## Findings
- **File**: `tradingview_scraper/utils/technicals.py`
- **Method**: `_safe_vote`
- **Evidence**:
  ```python
  v = pd.Series(0.0, index=index)
  v.loc[cond_buy.reindex(...).values] = 1.0
  ```
- **Impact**: Cumulative slowdown in large-scale backtests.

## Proposed Solutions

### Solution A: Vectorized Arithmetic (Recommended)
Replace the boolean indexing with integer arithmetic:
```python
# Assuming index alignment is already handled or inputs are reindexed once
v = (cond_buy.astype(int) - cond_sell.astype(int)).astype(float)
```
This reduces 4 dataframe operations to 3 numpy-level array operations.

## Technical Details
- Verify that `cond_buy` and `cond_sell` share the same index as the target.
- Refactor `_safe_vote` to use the subtraction method.

## Acceptance Criteria
- [ ] `_safe_vote` implementation uses vectorized subtraction.
- [ ] Logic correctly yields `1.0` (Buy), `-1.0` (Sell), and `0.0` (Neutral/Conflict).

## Work Log
- 2026-01-29: Issue identified by Performance Oracle.
