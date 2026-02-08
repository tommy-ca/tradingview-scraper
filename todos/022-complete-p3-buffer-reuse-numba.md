---
status: complete
priority: p3
issue_id: "022"
tags: ['performance', 'numba', 'optimization']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
Buffer Reuse in Numba. Currently, some JIT-compiled functions may be performing allocations inside loops, which leads to performance degradation due to repeated memory management overhead.

## Findings
- **Context**: Numba's `@njit` loops are most efficient when they operate on pre-allocated memory.
- **Issue**: Internal allocations within tight loops trigger Numba's memory allocator frequently.
- **Impact**: Increased latency and reduced throughput for high-frequency quantitative calculations (e.g., rolling metrics, entropy).

## Proposed Solutions

### Solution A: Pre-allocation (Recommended)
Pre-allocate buffers outside the JIT-compiled loop and pass them as arguments to the JIT function. This allows the JIT function to reuse the same memory space across iterations.

### Solution B: Internal Buffer Reuse
If passing buffers from outside is not feasible, use `np.empty` or similar inside the JIT function but structured in a way that Numba can optimize the allocation (though Solution A is generally superior).

## Recommended Action
Identify JIT loops in the codebase (e.g., in `utils/metrics.py` or `portfolio_engines`) and refactor them to accept pre-allocated buffers.

## Acceptance Criteria
- [x] JIT loops with internal allocations identified.
- [x] Refactored functions to use pre-allocated buffers passed as arguments.
- [x] Benchmarking confirms a reduction in execution time for affected functions.
- [x] All regression tests for affected metrics pass.

## Work Log
- 2026-02-02: Issue identified during P3 performance review. Created todo file.
- 2026-02-07: Implemented `compute_rolling_entropy_numba` in `predictability.py` using the "Out" parameter pattern for buffer reuse.
