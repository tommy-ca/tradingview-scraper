---
status: complete
priority: p1
issue_id: "085"
tags: [data-integrity, loader, migration]
dependencies: []
created_at: 2026-02-06
---

## Problem Statement
`DataLoader` is missing the fallback logic for `.pkl` files when `.parquet` is missing. This risks data loss for legacy runs that haven't been migrated.

## Findings
Reviewers noted that the fallback logic was absent in the latest version of `tradingview_scraper/data/loader.py`.

## Proposed Solutions
Restore the fallback logic: if `.parquet` is missing, try loading `.pkl` and log a warning.

## Acceptance Criteria
- [x] `DataLoader` loads `.pkl` if `.parquet` is absent.
- [x] Warning is logged on fallback.
