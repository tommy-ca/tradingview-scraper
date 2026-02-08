---
status: complete
priority: p2
issue_id: "056"
tags: [quality, anti-pattern, pydantic]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The code uses `object.__setattr__(selection, "winners", winners)` to force-update an immutable Pydantic model, bypassing validation and immutability guarantees.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py`: Line 228
- **Evidence**: `object.__setattr__(selection, "winners", winners)`

## Proposed Solutions

### Solution A: Use model_copy (Recommended)
Use `.model_copy(update={"winners": winners})` to create a new valid instance.

```python
selection = selection.model_copy(update={"winners": winners})
```

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] `object.__setattr__` usage removed.
- [ ] Code uses `model_copy` or `model_rebuild`.

## Work Log
- 2026-02-05: Identified during code quality review.
