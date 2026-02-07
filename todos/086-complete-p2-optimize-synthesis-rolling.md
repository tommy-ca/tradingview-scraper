---
status: complete
priority: p2
issue_id: "086"
tags: [performance, synthesis]
dependencies: []
created_at: 2026-02-06
---

## Problem Statement
`np.roll` is used in synthesis trend logic, which is inefficient. `pd.Series.shift` should be used instead.

## Findings
`tradingview_scraper/utils/synthesis.py` uses `np.roll` which creates copies and is less idiomatic than `shift`.

## Proposed Solutions
Replace `np.roll` logic with `pd.Series.shift(1).fillna(-1) > 0`.

## Acceptance Criteria
- [x] `np.roll` replaced with `shift`.
- [x] Logic correctness verified.
