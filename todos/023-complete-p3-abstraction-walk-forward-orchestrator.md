---
status: complete
priority: p3
issue_id: "023"
tags: ['refactor', 'architecture', 'backtest']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
Abstraction: WalkForwardOrchestrator. The current walk-forward simulation logic is tightly coupled with specific strategy implementations and logic. This makes it difficult to reuse the time-stepping logic across different backtest engines or for testing.

## Findings
- **Context**: Walk-forward analysis involves sliding or expanding windows of training and testing data.
- **Issue**: Time-stepping logic (calculating start/end dates for each fold) is repeated or embedded within execution loops.
- **Impact**: Increased complexity in `backtest_engine.py` and difficulty in implementing alternative validation schemes (e.g., Combinatorial Purged Cross-Validation).
- **Industry Standards**: Research into vectorbt, QuantConnect, and OpenBB confirms the benefit of decoupled window generation and "Recursive Meta-Portfolio" patterns.

## Proposed Solutions

### Solution A: Orchestrator Class (Recommended)
Extract the time-stepping logic into a dedicated `WalkForwardOrchestrator` class. This class should take parameters like `lookback_days`, `step_size`, and `test_size`, and yield tuples of `(train_start, train_end, test_start, test_end)`.

### Solution B: Functional Generator
Implement a generator function that produces the window boundaries, allowing it to be easily integrated into existing loops with minimal refactoring.

## Recommended Action
Implement the `WalkForwardOrchestrator` in a new module (e.g., `tradingview_scraper/backtest/orchestration.py`) and refactor `backtest_engine.py` to use it.

## Acceptance Criteria
- [x] `WalkForwardOrchestrator` class implemented with support for fixed and expanding windows.
- [x] Existing walk-forward loops in `backtest_engine.py` refactored to use the orchestrator.
- [x] Unit tests covering edge cases like short history, leap years, and different step sizes.
- [x] Support for non-contiguous windows via `SequenceOrchestrator`.

## Work Log
- 2026-02-02: Issue identified during P3 architectural review. Created todo file.
- 2026-02-02: Implemented `WalkForwardOrchestrator` and `RecursiveMetaOrchestrator` in `tradingview_scraper/backtest/orchestration.py`. Refactored `scripts/backtest_engine.py` to use the new abstraction.
- 2026-02-07: Further abstracted window generation to support non-contiguous windows via `SequenceOrchestrator` and `_get_step_indices` hook.
