---
status: complete
priority: p2
issue_id: "056"
tags: [code-review, architecture, data-consistency]
dependencies: ["053"]
---

# Problem Statement
The selection pipeline is inconsistent with the backtesting engine because it does not load point-in-time features from the `features_matrix.parquet` created during the DataOps cycle.

# Findings
- `BackfillService` creates a high-fidelity PIT feature matrix.
- `DataLoader` uses this matrix for backtesting.
- The `IngestionStage` in the selection pipeline ignores this matrix, relying only on live/cached candidate metadata.

# Proposed Solutions
1. **Connect Ingestion to Parquet**: Update `IngestionStage` to load and merge data from `features_matrix.parquet` if available.
2. **Unified Data Loader**: Force both selection and backtesting to use the same `DataLoader` method for feature retrieval.

# Resolution
- Modified `tradingview_scraper/pipelines/selection/stages/ingestion.py` to:
    - Resolve the path to `features_matrix.parquet` (checking run directory then lakehouse).
    - Load the features matrix into `context.feature_store`.
    - Align the features with the last timestamp of `returns_matrix`.
    - Merge PIT features (`recommend_all`, `recommend_ma`, `recommend_other`) into the `context.raw_pool` candidate dictionaries, prioritizing them over live snapshot values.

# Acceptance Criteria
- [x] Selection pipeline verified to use PIT features from Parquet.
- [x] Parity achieved between selection features and backtesting features.

# Work Log
### 2026-02-04 - Finding Created
**By:** Claude Code
- Architectural inconsistency identified between pipeline stages.

### 2026-02-04 - Resolution Implemented
**By:** Antigravity
- Implemented `_resolve_features_path` in `IngestionStage`.
- Added logic to `execute` to load `features_matrix.parquet`.
- Implemented PIT feature merging logic with timestamp alignment.

