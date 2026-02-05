---
status: pending
priority: p1
issue_id: "063"
tags: [data-integrity, bug, critical, migration]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `migrate_pickle_to_parquet.py` script contains a critical data integrity issue in its JSON serialization logic. It fails to handle `np.ndarray` (converting it to string representation `"[1 2 3]"`) and `np.bool_` (converting to string `"True"`/`"False"`).

## Findings
- **Location**: `scripts/maintenance/migrate_pickle_to_parquet.py`: Lines 100-108
- **Issue**: `default(o)` handler falls through to `str(o)` for arrays and numpy booleans.
- **Impact**: Irreversible data structure loss. Lists become strings. Booleans become strings.

## Proposed Solutions

### Solution A: Comprehensive Numpy Handler (Recommended)
Update the `default` handler to check for `np.ndarray` (return `.tolist()`) and `np.bool_` (return `bool()`).

```python
if isinstance(o, np.ndarray):
    return o.tolist()
if isinstance(o, np.bool_):
    return bool(o)
```

## Recommended Action
Implement Solution A immediately.

## Acceptance Criteria
- [ ] `np.ndarray` serializes as JSON list.
- [ ] `np.bool_` serializes as JSON boolean.
- [ ] Verify using `reproduce_json_numpy.py`.

## Work Log
- 2026-02-05: Identified during data integrity review.
