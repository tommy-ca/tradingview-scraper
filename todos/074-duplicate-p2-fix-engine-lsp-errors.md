---
status: pending
priority: p2
issue_id: "074"
tags: [quality, type-checking, lsp, engine]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
Static analysis (LSP) has identified multiple type mismatches and attribute access errors in `tradingview_scraper/backtest/engine.py`. These include return type mismatches, argument type incompatibilities, and accessing unknown attributes on `ndarray`.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py`
- **Errors**:
    - `Type "Series | Unknown | DataFrame" is not assignable to return type "DataFrame"`
    - `Argument ... cannot be assigned to parameter "bench_rets" of type "Series | None"`
    - `Type "tuple[str | float, ...]" is not assignable to return type "tuple[str, str]"`
    - `Cannot access attribute "sort_index" for class "ndarray[_AnyShape, dtype[Any]]"`

## Proposed Solutions

### Solution A: Fix Types and Casts (Recommended)
- Update return type hints where appropriate.
- Use explicit `cast(pd.DataFrame, ...)` or `cast(pd.Series, ...)` where logic guarantees the type but static analysis fails.
- Fix tuple return types to match signature.
- Check why `sort_index` is called on an `ndarray` (likely a result of `pd.concat` returning something unexpected or type inference failure) and cast/convert to DataFrame/Series if needed.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] LSP errors resolved in `backtest/engine.py`.

## Work Log
- 2026-02-05: Identified during code review.
