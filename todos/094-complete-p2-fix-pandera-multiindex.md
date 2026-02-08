---
status: complete
priority: p2
issue_id: "094"
tags: [integrity, pandera, validation]
dependencies: []
---

# Fix Pandera MultiIndex Support

## Problem Statement
The current Pandera schemas in `contracts.py` enforce an integer index, which will fail on institutional returns matrices that use `DatetimeIndex` or `MultiIndex` (e.g., `[Symbol, Date]`).

## Findings
- **Location**: `tradingview_scraper/pipelines/contracts.py`
- **Issue**: `index=pa.Index(int)` is too restrictive.

## Proposed Solutions

### Solution A: Flexible Index Validation
Update schemas to support `pd.DatetimeIndex` and allow for `MultiIndex` levels if the stage requires it.

## Recommended Action
Relax index constraints and add timezone/UTC awareness checks to the schema.

## Acceptance Criteria
- [ ] Schemas pass on standard `BacktestEngine` returns matrices.
- [ ] No `KeyError` on "date" column check (use index instead).

## Work Log
- 2026-02-07: Identified during integrity review.
