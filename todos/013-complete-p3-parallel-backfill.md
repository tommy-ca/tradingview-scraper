---
status: complete
priority: p3
issue_id: "013"
tags: ['performance', 'ray', 'parallelization']
dependencies: []
created_at: 2026-02-01
---

## Problem Statement
The `scripts/services/backfill_features.py` script currently processes symbols sequentially in a single-threaded loop. For large universes (e.g., 500+ symbols), this becomes a bottleneck in the production pipeline, especially when calculating complex technical indicators.

## Findings
- **File**: `scripts/services/backfill_features.py`
- **Location**: Lines 80-128
- **Evidence**:
  ```python
  for symbol in symbols:
      # Sequential processing of each symbol's parquet file
      df = pd.read_parquet(file_path)
      # ... technical calculations ...
      all_features[(symbol, "recommend_ma")] = ma
  ```
- **Context**: The platform already utilizes `RayComputeEngine` for other parallel tasks (e.g., selection, optimization), making it the natural choice for parallelizing symbol-level feature calculation.

## Proposed Solutions

### Solution A: Use `RayComputeEngine` (Recommended)
Refactor the symbol processing logic into a standalone function and use `RayComputeEngine` to distribute the workload. This leverages existing infrastructure and ensures consistent resource management.

### Solution B: `concurrent.futures.ProcessPoolExecutor`
Use Python's standard library for local multiprocessing. Simpler but lacks the distributed capabilities and telemetry integration provided by `RayComputeEngine`.

## Recommended Action
Refactor `backfill_features.py` to use `RayComputeEngine` for parallel symbol processing. Wrap the logic from lines 80-128 into a `_process_single_symbol_task`.

## Acceptance Criteria
- [x] Processing logic extracted into a parallelizable task.
- [x] `RayComputeEngine` integrated into the script lifecycle.
- [x] Telemetry/logging shows distributed execution traces.
- [x] Significant reduction in execution time for large universes.
- [x] Feature matrix output remains bit-identical to sequential version.

## Work Log
- 2026-02-01: Issue identified during P3 findings review. Created todo file.
- 2026-02-07: Refactored `backfill_features.py` to use Ray via `RayComputeEngine`. Extracted processing logic into `_process_single_symbol_task`.
