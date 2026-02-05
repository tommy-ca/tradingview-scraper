---
status: complete
priority: p1
issue_id: "047"
tags: [performance, numba, backtest]
dependencies: []
---

# Problem Statement
The `NumericalWorkspace` was introduced to eliminate GC pressure via zero-allocation JIT kernels, but it is currently allocated in `BacktestEngine` and never passed to the actual `predictability.py` functions or solvers.

# Findings
- `BacktestEngine` allocates `self.workspace` but `_run_window_step` calls `selection_engine.select` and `self.synthesizer.synthesize` without passing it.
- `predictability.py` kernels default to allocating new buffers if `None` is passed.

# Proposed Solutions
1. Update `BaseSelectionEngine.select` and `MarketRegimeDetector.detect_regime` to accept an optional `workspace`.
2. Pass `self.workspace` from `BacktestEngine` through the selection and synthesis stages.

# Acceptance Criteria
- [x] `calculate_permutation_entropy` receives buffers from the workspace.
- [x] No new allocations occur in the hot loop.

# Work Log
- 2026-02-05: Verified `workspace` is passed from `BacktestEngine` through `_run_window_step` to `StrategySynthesizer`. AC checked.
