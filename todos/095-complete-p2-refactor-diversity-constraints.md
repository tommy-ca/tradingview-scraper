---
status: complete
priority: p2
issue_id: "095"
tags: [architecture, srp, risk]
dependencies: []
---

# Refactor Diversity Constraints (SRP Violation)

## Problem Statement
The `BacktestEngine` contains hardcoded risk management logic (`_apply_diversity_constraints` with 25% caps), violating the Single Responsibility Principle.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py:421-432`
- **Issue**: Logic leakage from Risk Layer into Orchestrator.

## Proposed Solutions

### Solution A: Move to Risk Module
Move the logic to `tradingview_scraper/risk/constraints.py` (already created, but ensure logic is fully migrated and configurable).

## Recommended Action
Complete the migration of risk constraints.

## Acceptance Criteria
- [x] `_apply_diversity_constraints` removed from `BacktestEngine`.
- [x] Caps are configurable via `settings.cluster_cap`.
- [x] Hardcoded caps removed from Portfolio Engines (skfolio, riskfolio, custom).
- [x] Logic improved using institutional simplex projection in Risk Module.

## Work Log
- 2026-02-07: Identified during architecture review.
- 2026-02-08: Migrated logic to `risk/constraints.py`, removed hardcoded caps in engines, and updated `BacktestEngine` to use configurable settings.
