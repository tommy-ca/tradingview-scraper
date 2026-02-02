---
status: complete
priority: p2
issue_id: "010"
tags: [performance, numba]
dependencies: ["003"]
---

# Numba Dictionary Bottleneck in permutation_entropy

The `_calculate_permutation_entropy_jit` function in `tradingview_scraper/utils/predictability.py` uses a Python dictionary inside a JIT-compiled loop, which is a significant performance bottleneck and counter-productive for Numba optimization.

## Problem Statement

- Numba support for Python dictionaries in `njit` mode is suboptimal and slower than array-based operations.
- The current implementation uses `perm_counts = {}` to store permutation frequencies.
- Dictionary lookups and updates inside the main loop (lines 129-146) negate much of the benefit of using JIT compilation.
- For a small `order` (e.g., 3 or 5), the number of possible permutations is small (3! = 6, 5! = 120), making array-based indexing far more efficient.

## Findings

- **File**: `tradingview_scraper/utils/predictability.py:103`
- **Logic**:
    - Line 126: `perm_counts = {}`
    - Line 143: `if key in perm_counts: perm_counts[key] += 1`
- **Impact**: Increased latency in the selection pipeline, especially when calculating entropy for large universes and long lookbacks.

## Proposed Solutions

### Option 1: Array-based Indexing (Lehmer Code)
**Approach:** Map each permutation to a unique integer index in the range `[0, order! - 1]` using the Lehmer code or a similar ranking algorithm. Use a fixed-size NumPy array `perm_counts = np.zeros(math.factorial(order))` for counting.

**Pros:**
- Extreme performance improvement (O(1) array access vs dictionary lookup).
- Fully compatible with Numba's most efficient optimizations.

**Cons:**
- Requires implementing a permutation-to-index mapping function within Numba.

**Effort:** 2-3 hours
**Risk:** Low

---

### Option 2: Pre-allocated Hash Table
**Approach:** Use a fixed-size array as a simple hash table if a direct mapping is too complex to implement.

**Pros:**
- Still faster than a Python dictionary.

**Cons:**
- Risk of collisions or wasted space.
- Less elegant than a direct mapping.

**Effort:** 1-2 hours
**Risk:** Low

## Recommended Action

**To be filled during triage.** Implement Option 1 (Lehmer code mapping).

## Technical Details

**Affected files:**
- `tradingview_scraper/utils/predictability.py:103` - `_calculate_permutation_entropy_jit`

## Acceptance Criteria

- [ ] `perm_counts` changed from `dict` to `np.ndarray`.
- [ ] Dictionary operations removed from the JIT loop.
- [ ] Benchmarking shows >5x speedup for `calculate_permutation_entropy`.
- [ ] Results remain mathematically identical to the current implementation.

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Identified dictionary usage in `_calculate_permutation_entropy_jit`.
- Verified that `order` is typically small, making array indexing feasible.
- Created todo entry 010.

## Notes

- This issue is a follow-up to the initial JIT implementation in issue 003.
- Lehmer code mapping is a standard way to rank permutations.
