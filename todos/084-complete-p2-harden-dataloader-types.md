---
status: complete
priority: p2
issue_id: "084"
tags: [quality, type-safety, dataloader]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
`DataLoader.load_run_data` currently returns a raw `dict[str, Any]`. This is "stringly typed" and error-prone.

## Findings
- **Reviewer**: Kieran Rails Reviewer
- **Issue**: Lack of type safety.

## Proposed Solutions

### Solution A: Typed Return Object (Recommended)
Introduce a `RunData` dataclass or Pydantic model.

```python
@dataclass
class RunData:
    returns: pd.DataFrame
    features: pd.DataFrame
    metadata: dict
```

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [x] `DataLoader` returns typed object.
- [x] Docstrings updated.

## Work Log
- 2026-02-05: Identified during plan review.
