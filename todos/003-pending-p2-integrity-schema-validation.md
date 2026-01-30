---
status: pending
priority: p2
issue_id: 003
tags: ['data-integrity', 'validation']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `scripts/services/backfill_features.py` script constructs a feature dataframe but does not strictly validate it against the `FeatureStoreSchema` defined in `contracts.py` before saving. While the logic *should* be safe, an explicit check prevents corrupted data (e.g., values > 1.0 due to a logic bug) from polluting the Lakehouse.

## Findings
- **File**: `scripts/services/backfill_features.py`
- **Missing**: No explicit call to `FeatureStoreSchema.validate()`.
- **Risk**: Silent data corruption if upstream calculations change.

## Proposed Solutions

### Solution A: Explicit Validation
Import `FeatureStoreSchema` from `pipelines.contracts` and call `.validate()` on the final DataFrame before `to_parquet`.

### Solution B: Safe Schema Projection
Ensure the DataFrame columns strictly match the schema fields, dropping any extra debug columns that might have leaked in.

## Technical Details
- Add import: `from tradingview_scraper.pipelines.contracts import FeatureStoreSchema`
- Add validation block inside the persist function.

## Acceptance Criteria
- [ ] `FeatureStoreSchema.validate(features_df)` is called before save.
- [ ] Invalid data raises a `SchemaError` and halts the write (or logs a warning depending on strictness policy).

## Work Log
- 2026-01-29: Issue identified by Data Integrity Guardian.
