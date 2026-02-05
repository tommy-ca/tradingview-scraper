---
status: pending
priority: p3
issue_id: "059"
tags: [quality, refactor, circular-dependency]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `BacktestEngine` contains a local import `from tradingview_scraper.regime import MarketRegimeDetector` inside `__init__`, indicating a circular dependency workaround.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py`: Line 66
- **Issue**: Local imports inside methods/constructors make code harder to test and reason about.

## Proposed Solutions

### Solution A: Dependency Injection (Recommended)
Inject `MarketRegimeDetector` (or a factory) into `BacktestEngine` constructor.

### Solution B: Refactor Modules
Move `MarketRegimeDetector` or `BacktestEngine` to break the cycle.

## Recommended Action
Implement Solution A if feasible, or B.

## Acceptance Criteria
- [ ] Local import removed.
- [ ] Circular dependency resolved.

## Work Log
- 2026-02-05: Identified during code quality review.
