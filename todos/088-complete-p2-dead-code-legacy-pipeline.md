---
status: complete
priority: p2
issue_id: "088"
tags: [cleanup, quality]
dependencies: []
created_at: 2026-02-06
---

## Problem Statement
`pipeline_legacy.py` is unused and confusing.

## Findings
Reviewer identified this file as dead code.

## Proposed Solutions
Delete `tradingview_scraper/pipeline_legacy.py` and its tests.

## Acceptance Criteria
- [x] `tradingview_scraper/pipeline_legacy.py` deleted.
- [x] Associated tests (e.g., `tests/test_pipeline.py`) deleted.
