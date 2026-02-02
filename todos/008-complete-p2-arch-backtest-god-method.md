---
status: complete
priority: p2
issue_id: "008"
tags: [architecture, refactor]
dependencies: []
---

# God Method Refactor: BacktestEngine.run_tournament

The `BacktestEngine.run_tournament` method in `scripts/backtest_engine.py` is a "God Method" that has grown to over 450 lines (line 229 to 678), violating the Single Responsibility Principle and making maintenance difficult.

## Problem Statement

- `BacktestEngine.run_tournament` handles too many responsibilities: rolling window logic, universe filtering, regime detection, strategy synthesis, portfolio optimization, simulation, and artifact persistence.
- High cyclomatic complexity makes it difficult to unit test individual components of the backtest loop.
- The method is brittle and hard to extend with new features without risking regression in existing logic.

## Findings

- **File**: `scripts/backtest_engine.py:229`
- **Current Length**: ~450 lines.
- **Responsibilities identified**:
    1. Recursive meta-backtest initialization (lines 252-275).
    2. Profile/Engine/Simulator resolution (lines 277-296).
    3. Audit ledger management (line 302).
    4. Rolling window loop (lines 313-643).
    5. Dynamic universe filtering (lines 318-363).
    6. Regime detection (lines 366-378).
    7. Pillar 1: Universe Selection (lines 380-437).
    8. Pillar 2: Strategy Synthesis (lines 439-445).
    9. Pillar 3: Allocation / Optimization with Adaptive Ridge loop (lines 447-571).
    10. Backtest Simulation (lines 572-636).
    11. Artifact persistence and stitched returns construction (lines 645-678).

## Proposed Solutions

### Option 1: Extract Responsibility Classes
**Approach:** Decompose the loop into distinct "Stage" objects or methods (e.g., `SelectionStage`, `OptimizationStage`, `SimulationStage`) that the main loop coordinates.

**Pros:**
- Maximum testability.
- Clear separation of concerns.

**Cons:**
- Requires significant refactoring of state management.

**Effort:** 6-8 hours
**Risk:** Medium

---

### Option 2: Componentize as Private Methods
**Approach:** Extract the major blocks within `run_tournament` into private helper methods within `BacktestEngine` (e.g., `_run_selection_stage`, `_run_optimization_stage`).

**Pros:**
- Easier to implement than full class extraction.
- Immediately improves readability.

**Cons:**
- Still keeps the state coupled to the `BacktestEngine` class.

**Effort:** 3-4 hours
**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `scripts/backtest_engine.py:229` - `run_tournament` method

## Acceptance Criteria

- [ ] `run_tournament` reduced to < 100 lines.
- [ ] Major stages extracted into separate methods or classes.
- [ ] Unit tests added for extracted components.
- [ ] Full backtest tournament produces identical results to current implementation.

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Analyzed `scripts/backtest_engine.py` and identified the 450-line God Method.
- Mapped out the 11 distinct responsibilities currently handled by `run_tournament`.
- Created todo entry 008.

## Notes

- This refactor is critical for long-term maintainability as we add more complex selection and optimization logic.
- Consider using a "Context" object to pass state between extracted stages.
