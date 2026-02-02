---
category: performance-issues
tags: [numba, jit, optimization, bottleneck, quant]
module: shared-utils
symptoms: [slow-jit-execution, high-latency-backfill]
---

# Numba Dictionary Bottleneck Optimization

## Problem
The `_calculate_permutation_entropy_jit` function in `tradingview_scraper/utils/predictability.py` suffered from significant performance degradation when processing large asset universes. Despite being JIT-compiled with Numba, the execution speed was sub-optimal for high-frequency rolling window calculations.

## Root Cause
The JIT-compiled loop was using a Python-style dictionary (`perm_counts = {}`) to count permutation occurrences. In Numba's `njit` mode:
1.  **Dictionary Hashing**: Hashing keys and managing the dictionary structure inside a high-frequency loop incurs significant overhead.
2.  **Dynamic Allocation**: Frequent updates to the dictionary can trigger re-allocations and overhead that bypass the benefits of machine-code compilation.

## Solution
Replaced the dictionary-based counting with a fixed-size NumPy array and a deterministic encoding scheme.

### 1. Base-Order Encoding
Mapped each permutation (of size `order`) to a unique integer index using base-order encoding. For an `order=5` (default), the maximum key is $5^5 = 3125$.

```python
key = 0
for val in perm_idx:
    key = key * order + val
```

### 2. Fixed-Size Array Indexing
Pre-allocated a fixed-size NumPy array (`perm_counts = np.zeros(4000, dtype=np.int32)`) to hold counts. This replaces hash lookups with direct memory access (O(1)).

### 3. Iterative Efficiency
The entropy calculation now iterates over the fixed-size array, skipping zero entries, which is highly efficient in compiled code.

## Verification Results
- **Benchmark**: Significant speedup observed compared to the dictionary-based JIT implementation.
- **Accuracy**: Verified that the new array-based logic produces identical results to the dictionary-based logic through `tests/test_predictability.py`.

## Related Issue
- `todos/010-complete-p2-perf-entropy-bottleneck.md`
