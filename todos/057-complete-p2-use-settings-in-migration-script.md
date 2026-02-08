---
status: complete
priority: p2
issue_id: "057"
tags: [quality, hardcoded-paths, maintenance]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `migrate_pickle_to_parquet.py` script hardcodes the data directory path, making it brittle to configuration changes.

## Findings
- **Location**: `scripts/maintenance/migrate_pickle_to_parquet.py`: Line 36
- **Evidence**: `Path("data").resolve()`

## Proposed Solutions

### Solution A: Use Settings (Recommended)
Import `get_settings` and use `settings.data_dir`.

```python
from tradingview_scraper.settings import get_settings
settings = get_settings()
base_dir = settings.data_dir
```

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] Hardcoded path removed.
- [ ] Script uses `settings.data_dir`.

## Work Log
- 2026-02-05: Identified during code quality review.
