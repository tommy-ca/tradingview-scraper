---
status: completed
priority: p2
issue_id: 005
tags: ['performance', 'code-quality', 'refactor']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The feature engineering stage in `tradingview_scraper/pipelines/selection/stages/feature_engineering.py` uses nested loops and cell-by-cell `loc` assignments to construct the feature matrix. This is an O(N×M) operation in Python, which is inefficient and non-idiomatic for Pandas.

## Findings
- **File**: `tradingview_scraper/pipelines/selection/stages/feature_engineering.py`
- **Issue**: Nested loops and non-vectorized metadata extraction.
- **Risk**: Poor performance on large universes; hard to read/maintain.

## Proposed Solutions

### Solution A: Vectorized Construction (Recommended)
Construct the full dictionary or list of data first, then call `pd.DataFrame(data)` once. Use `join` or `concat` to merge with existing data.

### Solution B: Bulk Updates
Use `pd.DataFrame.update()` if modifying in place.

## Technical Details
- Refactor `execute` method.
- Remove nested loops over symbols/features.
- Use `pd.concat` and `combine_first` for PIT feature overlay.

## Acceptance Criteria
- [x] No nested loops for DataFrame construction.
- [x] `get_feature_value` usage is minimized or vectorized (obsolete/removed).
- [x] Unit tests pass with new implementation.

## Work Log
- 2026-01-29: Issue identified by Pattern Recognition Specialist.
- 2026-02-01: Vectorized `FeatureEngineeringStage` metadata extraction. Implemented `calculate_liquidity_score_vectorized` in `scoring.py`. Also vectorized `SelectionEngineV3` and `SelectionEngineV2`.
