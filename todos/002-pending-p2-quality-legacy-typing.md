---
status: pending
priority: p2
issue_id: 002
tags: ['code-quality', 'python', 'refactor']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
`tradingview_scraper/futures_universe_selector.py` uses legacy Python typing (`List`, `Dict`, `Optional`) despite running on Python 3.10+. This clutters function signatures and goes against the project's modern Python standards. Additionally, the file is becoming a "God Object" (1800+ lines) mixing CLI parsing, data models, and business logic.

## Findings
- **File**: `tradingview_scraper/futures_universe_selector.py`
- **Issue**: Ubiquitous usage of `from typing import List, Dict, Optional`.
- **Complexity**: `_aggregate_by_base` is 120 lines long with mixed concerns.
- **Organization**: Pydantic models consume the first ~230 lines.

## Proposed Solutions

### Solution A: Modernize Typing (Immediate)
Run a global refactor to replace legacy types with built-ins:
- `List[str]` -> `list[str]`
- `Dict[str, Any]` -> `dict[str, Any]`
- `Optional[float]` -> `float | None`

### Solution B: Structural Refactor (Follow-up)
Extract Pydantic models to `tradingview_scraper/schemas/selector.py` to declutter the main logic file.

## Technical Details
- Use `sed` or manual edit to update type hints.
- Verify `mypy` or `pyright` passes after changes.

## Acceptance Criteria
- [ ] No imports of `List`, `Dict`, `Optional` from `typing`.
- [ ] All signatures use `| None` for optionals.
- [ ] Code passes syntax check.

## Work Log
- 2026-01-29: Issue identified by Kieran Python Reviewer.
