---
category: logic-errors
tags: [refactoring, srp, design-patterns, clean-code]
module: orchestration
symptoms: [parameter-bloat, code-smell, maintainability-debt]
---

# Addressing Parameter Bloat: Stateful Orchestrator Pattern

## Problem
Extracted helper methods in the `BacktestEngine` (like `_process_optimization_window`) were accepting up to 20 parameters. This excessive "parameter bloat" made the code difficult to read, test, and maintain, violating clean code principles.

## Root Cause
The `run_tournament` method was passing backtest-scoped configurations (constants like `sim_names`, `lightweight`) and accumulators (stateful objects like `results`, `return_series`) to its sub-methods on every call. These were treated as local variables in the main loop instead of part of the engine's internal state for that run.

## Solution
Implemented the **Stateful Orchestrator Pattern** by promoting backtest-scoped variables to instance variables (`self.X`) during the `run_tournament` lifecycle.

### Key Refactorings
1.  **Consolidated Constants**: Config parameters (`profiles`, `engines`, `sim_names`) are set once on the instance at the start of the run.
2.  **Consolidated Accumulators**: Data structures for tracking progress (`results`, `return_series`, `current_holdings`) are initialized as instance variables.
3.  **Simplified Signatures**: Sub-methods now access these variables via `self`, reducing parameter counts by ~50% (from 20+ to ~8).

### Implementation Logic
```python
class BacktestEngine:
    def run_tournament(self, ...):
        # 1. Promote locals to state for this run
        self.results = []
        self.return_series = {}
        # ...
        
        for window in windows:
            # 2. Sub-methods now have lean signatures
            self._process_optimization_window(window, train_rets, ...)
```

## Impact
- **Maintainability**: New parameters can be added to the run state without breaking dozens of method signatures.
- **SRP Compliance**: The orchestrator now truly "owns" the run state rather than just passing it around.
- **Clarity**: The main loop is significantly more readable, focusing on the high-level quantitative flow rather than data plumbing.

## Related Issues
- `todos/017-pending-p1-parameter-bloat-optimization.md`
- `docs/solutions/logic-errors/god-method-refactor-BacktestEngine-20260201.md`
