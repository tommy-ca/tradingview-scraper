---
status: complete
priority: p2
issue_id: "093"
tags: [architecture, refactor, pillar-3]
dependencies: []
---

# Extract AllocationPipeline (Triple-Pipeline Vision)

## Problem Statement
The "Triple-Pipeline" vision is incomplete. While Discovery and Selection are modular, the Allocation (Pillar 3) logic is still embedded as private methods within the `BacktestEngine` god object.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py`
- **Issue**: Pillar 3 logic lacks a dedicated pipeline class, violating architectural symmetry.

## Proposed Solutions

### Solution A: Modularize Allocation
Create `tradingview_scraper/pipelines/allocation/pipeline.py` and move `_execute_allocation`, `_process_optimization_window`, and `_run_simulation` into discrete `Stages`.

## Recommended Action
Execute the refactor to decouple Pillar 3 from the engine.

## Acceptance Criteria
- [x] `AllocationPipeline` exists and is registered in `StageRegistry`.
- [x] `BacktestEngine` is reduced to a "Coordinator" role.

## Work Log
- 2026-02-07: Identified during architecture review.
- 2026-02-08: Decoupled Pillar 3 into `AllocationPipeline` and modular stages. Refactored `BacktestEngine` to coordinate via the new pipeline.
