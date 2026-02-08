---
status: complete
priority: p1
issue_id: "098"
tags: [architecture, cleanup, backtest]
dependencies: []
---

## Problem Statement
`BacktestEngine` still relies on legacy selection logic in `_execute_selection` and does not yet call the modernized `SelectionPipeline`. This creates a "split-brain" state where the engine logic may drift from the modular pipeline logic.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py:223`
- **Issue**: High coupling and logic duplication. The engine still manually manages selection request/response instead of delegating to the specialized pipeline.

## Proposed Solutions

### Solution A: Unify Pillar 1 & 2 via SelectionPipeline (Recommended)
Refactor `BacktestEngine._run_window_step` to call `SelectionPipeline.run()`.

**Pros:**
- Eliminates legacy selection logic.
- Single source of truth for alpha selection.
- Completes the triple-pipeline integration.

## Recommended Action
Implement Solution A. Ensure the engine passes the necessary context and parameters to the modular pipeline.

## Acceptance Criteria
- [x] Legacy `_execute_selection` method removed from `BacktestEngine`.
- [x] Engine successfully delegates to `SelectionPipeline`.
- [x] Tournament results match baseline.

## Work Log
- 2026-02-07: Identified during architectural review by Antigravity.
- 2026-02-08: Refactored `BacktestEngine._run_window_step` to use `SelectionPipeline.run_with_data`. Removed legacy `_execute_selection` and updated audit logging to consume `SelectionContext`.
