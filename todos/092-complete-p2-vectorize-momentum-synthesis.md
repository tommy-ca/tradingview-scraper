---
status: complete
priority: p2
issue_id: "092"
tags: [performance, vectorization, synthesis]
dependencies: []
---

# Inefficient Momentum Synthesis (Python Loop Bottleneck)

## Problem Statement
The momentum synthesis logic uses `.rolling().apply(roll_prod)`, which triggers a Python function call for every window. This is several orders of magnitude slower than native NumPy vectorization.

## Findings
- **Location**: `tradingview_scraper/utils/synthesis.py`
- **Issue**: `rolling().apply()` bottleneck.

## Proposed Solutions

### Solution A: Log-Sum Vectorization (Recommended)
Use `np.log1p(rets).cumsum()` to calculate rolling returns in a single vectorized pass.

```python
log_rets = np.log1p(s_rets)
cum_log_rets = log_rets.cumsum()
mom = np.exp(cum_log_rets - cum_log_rets.shift(window)) - 1
```

## Recommended Action
Implement Solution A in `synthesis.py`.

## Acceptance Criteria
- [x] Momentum calculation is ~10x faster.
- [x] Numerical parity verified with existing implementation.

## Work Log
- 2026-02-07: Identified during performance review.
- 2026-02-08: Vectorized momentum calculation using log-sum-exp approach. Verified ~100x speedup for large datasets and confirmed numerical parity.
