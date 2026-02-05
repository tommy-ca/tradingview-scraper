---
status: complete
priority: p1
issue_id: "038"
tags: ['architecture', 'refactor']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
`backtest_engine.py` imports logic from `scripts/build_meta_returns.py`, which violates the core architectural principle that library code should not depend on scripts. Scripts should be thin wrappers around library logic.

## Findings
- **File**: `backtest_engine.py`
- **Issue**: Direct import from `scripts.*` namespace.
- **Impact**: Circular dependency risks, hard-to-test logic, and poor package boundary enforcement.

## Proposed Solutions

### Solution A: Extract Logic to Library
Move the meta-returns calculation logic from `scripts/build_meta_returns.py` to a dedicated module in the library (e.g., `tradingview_scraper/utils/meta_returns.py`).

## Recommended Action
Relocate meta-returns calculation logic to the library and update imports in `backtest_engine.py` and the existing script.

## Acceptance Criteria
- [x] `backtest_engine.py` no longer imports from the `scripts/` directory.
- [x] `scripts/build_meta_returns.py` refactored to use the new library module.
- [x] All tests for meta-returns pass after relocation.

## Work Log
- 2026-02-02: Issue identified as P1 finding. Created todo file.
- 2026-02-05: Verified `tradingview_scraper/utils/meta_returns.py` exists and is used by both scripts and engine. AC checked.
