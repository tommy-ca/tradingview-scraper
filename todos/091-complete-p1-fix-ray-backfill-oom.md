---
status: complete
priority: p1
issue_id: "091"
tags: [performance, scalability, ray, critical]
dependencies: []
---

# Ray Backfill Memory Bloat (Data Return Tax)

## Problem Statement
The `BackfillService` returns full `pd.Series` objects from Ray workers to the driver. At scale (1,000+ symbols), this will cause the driver node to exceed memory limits (OOM), as it attempts to collect and concatenate all series in-memory.

## Findings
- **Location**: `scripts/services/backfill_features.py`
- **Issue**: `_process_single_symbol_task` returns three full series per symbol.
- **Impact**: Projected memory usage for 5,000 symbols > 16GB.

## Proposed Solutions

### Solution A: Write-at-Edge (Recommended)
Have the Ray workers write their results directly to the Lakehouse (Parquet) and return only the file path or a success/fail status to the driver.

**Pros**: Constant memory usage on driver.
**Cons**: Requires handling concurrent writes (though each worker writes a unique file).

## Recommended Action
Refactor `BackfillService` to write Parquet files in the worker tasks.

## Acceptance Criteria
- [x] Driver memory usage remains stable during large-scale backfills.
- [x] Workers return `status: "success"` or paths, not DataFrames.

## Work Log
- 2026-02-07: Identified during performance review.
- 2026-02-08: Refactored `BackfillService` to write individual feature files in Ray tasks and collect paths. Implemented memory-efficient audit and consolidation. Verified with `tests/test_backfill_features.py`.
