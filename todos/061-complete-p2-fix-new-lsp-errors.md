---
status: complete
priority: p2
issue_id: "061"
tags: [quality, type-checking, lsp]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The newly created/modified files `meta_returns.py` and `backtest/engine.py` have multiple static analysis (LSP) errors, indicating potential runtime bugs or poor type hinting.

## Findings
- **Location**: `tradingview_scraper/utils/meta_returns.py`: `Cannot access attribute "to_frame" for class "float"`
- **Location**: `tradingview_scraper/backtest/engine.py`: Type mismatches in assignment and return types.

## Proposed Solutions

### Solution A: Fix Type Hints and Logic (Recommended)
Review the type hints and ensure they match the runtime types. Use `cast` if necessary, but prefer fixing the logic.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] LSP errors resolved in `meta_returns.py`.
- [ ] LSP errors resolved in `backtest/engine.py`.

## Work Log
- 2026-02-05: Identified during todo creation.
