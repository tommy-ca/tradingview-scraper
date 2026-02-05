---
status: complete
priority: p1
issue_id: "082"
tags: [security, data-integrity, loader, deprecation]
dependencies: []
created_at: 2026-02-05
completed_at: 2026-02-05
---

## Problem Statement
The current migration plan is risky because it enforces a hard cutover ("Ban `pd.read_pickle`") before ensuring all data is migrated. This could break workflows if the migration script fails on edge cases.

## Findings
- **Reviewer**: Kieran Rails Reviewer
- **Issue**: "Big Bang" migration risk.
- **Solution**: Implement "Support First, Migrate Second".

## Proposed Solutions

### Solution A: Hybrid Loader (Recommended)
Update `DataLoader` immediately to try loading `.parquet` first. If missing, attempt to load `.pkl` but log a `DeprecationWarning`.

### Solution B: Strict Loader
Only support `.parquet`. Break anything that hasn't been migrated. (Simpler, but risky).

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [x] `DataLoader.load_run_data` checks for `.parquet`.
- [x] If `.parquet` missing, checks for `.pkl`.
- [x] Logs warning on `.pkl` load.

## Work Log
- 2026-02-05: Identified during plan review.
- 2026-02-05: Implemented hybrid loader in `tradingview_scraper/data/loader.py`. Verified with reproduction script.
