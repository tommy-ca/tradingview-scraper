---
status: complete
priority: p3
issue_id: "015"
tags: ['refactor', 'utility', 'timezone']
dependencies: []
created_at: 2026-02-01
---

## Problem Statement
Timezone logic for ensuring a `DatetimeIndex` is UTC-aware and normalized is repeated across multiple files in the codebase. This leads to code duplication, increased maintenance burden, and potential inconsistencies if the logic needs to change (e.g., handling "contaminated" indices with mixed awareness).

## Findings
- **Files Affected**:
  - `scripts/services/backfill_features.py` (Line 101)
  - `scripts/prepare_portfolio_data.py` (Line 187)
  - `tradingview_scraper/portfolio_engines/nautilus_strategy.py` (Line 68)
  - `tradingview_scraper/utils/metrics.py` (Multiple locations)
  - `tradingview_scraper/portfolio_engines/impl/cvxportfolio.py` (Line 66)
- **Evidence**:
  ```python
  if df.index.tz is None:
      df.index = df.index.tz_localize("UTC")
  else:
      df.index = df.index.tz_convert("UTC")
  ```
  Or variations like:
  ```python
  df.index = pd.to_datetime(df.index).tz_localize(None).tz_localize("UTC")
  ```

## Proposed Solutions

### Solution A: Centralized `ensure_utc_index` Utility (Recommended)
Create a robust utility function `ensure_utc_index(df_or_series)` in a common module (e.g., `tradingview_scraper/utils/data.py` or similar). This function should handle:
1. Converting to `DatetimeIndex` if necessary.
2. Localizing naive indices to UTC.
3. Converting aware indices to UTC.
4. Handling "contaminated" indices by stripping existing tz info before re-applying UTC.

## Recommended Action
Implement `ensure_utc_index` and refactor the identified occurrences to use this shared utility.

## Acceptance Criteria
- [x] `ensure_utc_index` utility implemented with comprehensive error handling/edge case support.
- [x] At least 5 identified occurrences refactored to use the utility.
- [x] Unit tests covering naive, aware, and "contaminated" index scenarios.
- [x] No regression in data processing pipelines.

## Work Log
- 2026-02-01: Issue identified during P3 findings review. Created todo file.
- 2026-02-07: Refactored `backfill_features.py`, `prepare_portfolio_data.py`, `nautilus_strategy.py`, `metrics.py`, and `cvxportfolio.py` to use `ensure_utc_index` from `tradingview_scraper.utils.data_utils`.
