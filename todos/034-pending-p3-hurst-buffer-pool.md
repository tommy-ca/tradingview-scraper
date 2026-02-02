---
status: pending
priority: p3
issue_id: "034"
tags: ['performance', 'numba', 'memory']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
The `calculate_hurst_exponent` function in `tradingview_scraper/utils/predictability.py` allocates a `z_buffer` array on every single call. In high-throughput selection pipelines or rolling window calculations, this frequent allocation and subsequent garbage collection creates unnecessary overhead and memory pressure.

## Findings
- **File**: `tradingview_scraper/utils/predictability.py`
- **Location**: Line 78
- **Evidence**:
  ```python
  def calculate_hurst_exponent(x: np.ndarray) -> float | None:
      # ...
      # Pre-allocate buffer for JIT
      z_buffer = np.zeros(n_total)
      # ...
      rs = _get_rs_jit(segment, z_buffer)
  ```
- **Context**: While `_get_rs_jit` itself is optimized, its caller forces a new allocation. This pattern was recently improved for `calculate_permutation_entropy` but missed for Hurst.

## Proposed Solutions

### Solution A: Pass Buffer from Caller
Modify the function signature to accept an optional `z_buffer`. If not provided, it can still allocate locally for backward compatibility, but performance-critical paths can provide a pre-allocated buffer.

### Solution B: Thread-Local Buffer Pool
Implement a simple thread-local or object-based buffer pool that manages `np.ndarray` objects of various sizes, reducing allocation frequency.

## Recommended Action
Implement Solution A: Update `calculate_hurst_exponent` to accept `z_buffer: np.ndarray | None = None`. Update selection engines (`v3_mps.py`, `v2_cars.py`) and feature engineering pipelines to reuse buffers across symbols.

## Acceptance Criteria
- [ ] `calculate_hurst_exponent` supports an optional pre-allocated buffer.
- [ ] Major selection engines updated to reuse buffers.
- [ ] Unit tests verify that buffer reuse does not corrupt results (ensure buffer is correctly sliced or reset).
- [ ] Micro-benchmark shows reduction in allocation overhead.

## Work Log
- 2026-02-02: Issue identified during P3 findings review. Created todo file.
