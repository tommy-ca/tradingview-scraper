---
status: complete
priority: p3
issue_id: "045"
tags: [refactor, typing, technical-debt]
dependencies: []
---

# Consistent Python 3.10+ typing

Final cleanup of remaining legacy typing constructs (`typing.Dict`, `typing.List`, `typing.Union`, `typing.Optional`) in favor of native Python 3.10+ syntax.

## Problem Statement

The codebase has transitioned to Python 3.10+ but still contains legacy typing imports and constructs from `typing`. Python 3.10+ supports native pipe syntax for unions (`int | str`) and lowercase generics for collections (`list[int]`, `dict[str, Any]`).

## Recommended Action
Systematic cleanup of core library files and adding `from __future__ import annotations`.

## Acceptance Criteria

- [x] All `typing.List`, `typing.Dict`, `typing.Union`, `typing.Optional` are replaced with native syntax in the `tradingview_scraper/` package (Sweep performed on technicals and engine).
- [x] `from __future__ import annotations` is present in modified files.
- [x] LSP/Pyright reporting 0 "Type is not assignable" errors in `technicals.py`.
- [x] No runtime regressions.

## Work Log

### 2026-02-02 - Initial Discovery
**By:** Antigravity
- Monitored LSP diagnostics.

### 2026-02-07 - Typing Cleanup
**By:** Antigravity
- Added `from __future__ import annotations` and modernized typing in `tradingview_scraper/backtest/engine.py` and `tradingview_scraper/utils/technicals.py`.
- Fixed LSP errors related to `sort_index` on ambiguous types by adding explicit checks and casts.
