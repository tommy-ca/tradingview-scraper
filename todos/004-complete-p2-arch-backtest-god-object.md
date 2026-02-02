---
status: completed
priority: p2
issue_id: 004
tags: ['architecture', 'maintainability', 'refactor']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `BacktestEngine` in `scripts/backtest_engine.py` is evolving into a "God Object". It handles data loading, strategy inference (via magic strings), optimization, and result persistence. This violates the Single Responsibility Principle (SRP) and Open/Closed Principle (OCP), making it hard to add new strategies without modifying the core engine loop.

## Findings
- **File**: `scripts/backtest_engine.py`
- **Issue**: Hardcoded strategy logic:
  ```python
  if "mean_rev" in global_profile.lower(): ...
  ```
- **Issue**: Tightly coupled to specific optimization parameters based on profile names.

## Proposed Solutions

### Solution A: Strategy Factory Pattern
Extract strategy inference logic into a `StrategyFactory` or `ProfileConfig` class. The engine should receive a fully configured `StrategySpec` object, not raw strings.

### Solution B: Manifest-Driven Config
Move strategy mapping to `manifest.json`. The engine reads `strategy_type` from the manifest instead of inferring it from the profile name string.

## Technical Details
- Create `tradingview_scraper/orchestration/strategies.py` (or similar).
- Refactor `BacktestEngine.run` to delegate strategy creation.

## Acceptance Criteria
- [x] No "magic string" checks (`if "mean_rev" in ...`) in `BacktestEngine`.
- [x] Strategy parameters are passed in, not derived inside the loop.

## Work Log
- 2026-01-29: Issue identified by Architecture Strategist.
- 2026-02-01: Refactored strategy inference into `StrategyFactory`. Added `strategy` field to `TradingViewScraperSettings` and `manifest.json`.
