---
status: complete
priority: p1
issue_id: "054"
tags: [data-integrity, bug, critical, migration]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `migrate_pickle_to_parquet.py` script contains a critical data integrity issue in its JSON serialization logic. It converts all unknown types to strings, including `numpy.int64` and `numpy.float64`, which corrupts numerical data in metadata files.

## Findings
- **Location**: `scripts/maintenance/migrate_pickle_to_parquet.py`: Lines 99-102
- **Evidence**:
  ```python
  def default(o):
      if isinstance(o, (pd.Timestamp, pd.Period)):
          return str(o)
      return str(o)  # <--- CORRUPTS NUMPY NUMBERS
  ```
- **Impact**: Numerical metadata (e.g., counts, thresholds) becomes strings (e.g., `"42"` instead of `42`), causing downstream failures.

## Proposed Solutions

### Solution A: Handle Numpy Types Explicitly (Recommended)
Update the `default` handler to check for `np.integer` and `np.floating` and convert them to Python native `int` and `float`.

```python
import numpy as np
def default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    # ... handle timestamps ...
    return str(o)
```

## Recommended Action
Implement Solution A immediately to prevent data corruption during migration.

## Acceptance Criteria
- [x] JSON serialization correctly handles `numpy.int64` as `int`.
- [x] JSON serialization correctly handles `numpy.float64` as `float`.
- [x] Re-run migration test to verify metadata integrity.

## Work Log
- 2026-02-05: Identified during data integrity review.
