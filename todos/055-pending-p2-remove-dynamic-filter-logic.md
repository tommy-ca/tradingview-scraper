---
status: pending
priority: p2
issue_id: "055"
tags: [architecture, refactor, logic-leakage]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `_apply_dynamic_filter` method in `BacktestEngine` performs asset filtering based on the `recommend_all` feature before the actual Selection stage, violating the Single Responsibility Principle and leaking domain logic into the orchestrator.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py`: Lines 488-520
- **Issue**: Domain logic (recommend_all filtering) is hardcoded in the orchestration layer instead of being part of the configurable Selection Engine.

## Proposed Solutions

### Solution A: Move to Selection Engine (Recommended)
Refactor the logic into a new or existing `SelectionEngine` (e.g., `FundamentalSelectionEngine` or as a pre-filter step in `BaseSelectionEngine`).

**Pros:**
- Better separation of concerns.
- Configurable via `SelectionRequest`.

**Cons:**
- Requires refactoring the selection interface.

## Recommended Action
Implement Solution A. Move the logic to the Selection Engine.

## Acceptance Criteria
- [ ] `_apply_dynamic_filter` removed from `BacktestEngine`.
- [ ] Logic moved to `SelectionEngine`.
- [ ] Tests verify filtering still works.

## Work Log
- 2026-02-05: Identified during architecture review.
