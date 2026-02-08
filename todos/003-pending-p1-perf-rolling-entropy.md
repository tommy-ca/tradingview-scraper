---
status: pending
priority: p1
issue_id: 003
tags: ['performance', 'critical', 'backfill']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `scripts/services/backfill_features.py` script uses `rolling().apply()` with pure Python functions for calculating Entropy and Hurst exponents. This results in **O(N×W)** complexity with heavy Python interpreter overhead (loops, sorting, allocation) inside the rolling window. For a standard production run (500 assets, 500 days), this is a critical bottleneck causing 50-100x slowdowns.

## Findings
- **File**: `scripts/services/backfill_features.py`
- **Lines**: 71-79
- **Evidence**:
  ```python
  entropy = rets.rolling(win_short).apply(lambda x: calculate_permutation_entropy(x), raw=True)
  ```
- **Impact**: `calculate_permutation_entropy` uses `np.argsort` inside a python loop.
- **Risk**: High. Backfill jobs may time out or block CI/CD pipelines.

## Proposed Solutions

### Solution A: Numba JIT (Recommended)
Decorate the math functions in `tradingview_scraper/utils/technicals.py` (or where they are defined) with `@numba.jit(nopython=True)`. This compiles the loop to machine code, offering massive speedups.

### Solution B: Vectorized Approximation
Replace the exact rolling entropy with a vectorized approximation if exact precision isn't strictly required (unlikely for quant work).

## Technical Details
- Verify `numba` is in `requirements.txt`.
- Add `@jit` decorators to `calculate_permutation_entropy` and `calculate_hurst_exponent`.
- Ensure input types to JIT functions are compatible (numpy arrays).

## Acceptance Criteria
- [ ] `calculate_permutation_entropy` is JIT compiled.
- [ ] `calculate_hurst_exponent` is JIT compiled.
- [ ] Benchmark: Backfill for 1 symbol (1000 candles) takes < 100ms.

## Work Log
- 2026-01-29: Issue identified by Performance Oracle.
