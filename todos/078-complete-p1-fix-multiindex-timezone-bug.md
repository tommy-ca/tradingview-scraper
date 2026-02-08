---
status: complete
priority: p1
issue_id: "078"
tags: [bug, critical, data-integrity, migration]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The migration script `scripts/maintenance/migrate_pickle_to_parquet.py` fails to properly handle Timezone Normalization for `pd.MultiIndex` (e.g., Date/Symbol index). The check `isinstance(obj.index, pd.DatetimeIndex)` returns `False` for MultiIndex, causing the script to skip timezone localization, leaving artifacts with naive datetimes.

## Findings
- **Reviewer**: Kieran Rails Reviewer
- **Location**: `migrate_pickle_to_parquet.py`
- **Issue**: Implicit timezone logic fails for MultiIndex.

## Proposed Solutions

### Solution A: Recursive Index Level Check (Recommended)
Iterate through index levels. If a level is datetime-like and tz-naive, localize it.

### Solution B: Explode/Implode
Reset index, localize column, set index back. (Safer but slower).

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] Migration script correctly identifies `MultiIndex` with datetime levels.
- [ ] Datetime levels are localized to UTC.
- [ ] Validated with a test case involving `(Date, Symbol)` MultiIndex.

## Work Log
- 2026-02-05: Identified during plan review.
