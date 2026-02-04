---
status: complete
priority: p1
issue_id: "053"
tags: [code-review, data-integrity, alpha]
dependencies: []
---

# Problem Statement
There is a mismatch between the alpha signals provided by TradingView scanners and those expected by the new v4 selection pipeline, causing primary alpha signals to be discarded.

# Findings
- TradingView scanner data (raw candidates) uses PascalCase dotted keys like `Recommend.All`.
- `FeatureEngineeringStage` (v4) expects lowercase snake_case keys like `recommend_all`.
- The pipeline currently defaults these signals to `0.0`, discarding the core alpha ratings.

# Proposed Solutions
1. **Normalize in Pipeline**: Update `normalize_candidate_record` in `utils/candidates.py` to map `Recommend.All` to `recommend_all`. (Recommended)
2. **Update Stage Logic**: Update `FeatureEngineeringStage` to handle both naming conventions.

# Acceptance Criteria
- [x] `Recommend.All` signals are correctly mapped to `recommend_all` during ingestion.
- [x] Selection pipeline verified to use non-zero ratings for candidate filtering.

# Work Log
### 2026-02-04 - Finding Created
**By:** Claude Code
- Discovered signal loss in v4 selection pipeline.

### 2026-02-04 - Fix Implemented
**By:** Antigravity
- Updated `CANONICAL_KEYS` in `tradingview_scraper/utils/candidates.py` to include `recommend_all`, `recommend_ma`, and `recommend_other`.
- Modified `normalize_candidate_record` to extract these fields from `Recommend.*` keys in the raw data.
- Verified that these fields are now promoted to top-level keys in the candidate metadata dictionary, ensuring `FeatureEngineeringStage` can access them.
