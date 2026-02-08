---
status: complete
priority: p1
issue_id: "099"
tags: [performance, scalability, memory]
dependencies: []
---

## Problem Statement
The final consolidation of features in `backfill_features.py` uses `pd.concat` on a potentially massive list of DataFrames. For universes larger than 5,000 symbols with long histories, this will cause the driver node to exceed memory limits.

## Findings
- **Location**: `scripts/services/backfill_features.py:218`
- **Issue**: Memory bottleneck in matrix consolidation. `pd.concat` is a single-threaded operation that requires all constituents to be in memory.

## Proposed Solutions

### Solution A: Incremental Concatenation (Recommended)
Implement intermediate concatenation checkpoints. If the list of DataFrames exceeds 500, perform an intermediate concat to bound peak memory usage.

### Solution B: Transition to Tiled Storage
For $N > 10,000$, transition to a tiled format like Dask or Zarr that avoids driver-side consolidation.

## Recommended Action
Implement Solution A as a near-term guardrail.

## Acceptance Criteria
- [x] Driver memory usage monitored.
- [x] Intermediate concatenation reduces peak memory by >30% for large universes.

## Work Log
- 2026-02-07: Identified during performance review by Performance Oracle.
- 2026-02-08: Implemented Solution A (incremental concatenation) in `scripts/services/backfill_features.py`. (Antigravity)
