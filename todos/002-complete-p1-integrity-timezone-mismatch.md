---
status: complete
priority: p1
issue_id: 002
tags: ['data-integrity', 'critical', 'backfill']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `scripts/services/backfill_features.py` script strips timezones from the index (`tz_convert(None)`), while `tradingview_scraper/pipelines/contracts.py` explicitly mandates `datetime64[ns, UTC]` for returns and features. This mismatch causes index alignment failures (joins returning empty sets) and potential data corruption when merging backfilled features with live data.

## Findings
- **File**: `scripts/services/backfill_features.py`
- **Evidence**: explicit calls to `tz_convert(None)` in the worker logic.
- **Contract**: `ReturnsSchema` requires UTC-aware timestamps.
- **Risk**: High. Silent data loss during pipeline joins (inner joins on mismatched timezones).

## Proposed Solutions

### Solution A: Enforce UTC (Recommended)
Modify `_backfill_worker` to ensure the index is always UTC-localized.
```python
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC")
else:
    df.index = df.index.tz_convert("UTC")
```

### Solution B: Relax Contracts
Modify `contracts.py` to allow timezone-naive indices.
*Cons*: Regressive. Project standard is UTC. Breaks compatibility with other crypto-native components that rely on precise timestamps.

## Technical Details
- Edit `scripts/services/backfill_features.py`.
- Ensure `pd.read_parquet` or `pd.read_csv` result is immediately standardized to UTC.

## Acceptance Criteria
- [x] `backfill_features.py` output DataFrame has `UTC` timezone in index.
- [x] `validate_data_contracts` passes for the backfilled data.
- [x] Verify alignment with `returns` dataframe succeeds without dropping rows.

## Work Log
- 2026-01-29: Issue identified by Data Integrity Guardian.
- 2026-02-01: Fixed by enforcing UTC localization in `backfill_features.py`.
