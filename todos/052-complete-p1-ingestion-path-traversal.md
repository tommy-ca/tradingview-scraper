---
status: pending
priority: p1
issue_id: "052"
tags: [security, path-traversal, critical]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `IngestionStage` constructs filesystem paths using `SelectionContext.run_id` without validating it or ensuring the resolved path is within trusted boundaries. This allows potential path traversal if `run_id` is supplied via user input, bypassing the `settings.py` validation.

## Findings
- **Location**: `tradingview_scraper/pipelines/selection/stages/ingestion.py`: Lines 38 & 65
- **Evidence**:
  ```python
  run_data_dir = (settings.summaries_runs_dir / context.run_id / "data").resolve()
  ```
- **Risk**: High. If `run_id` is `../../../etc`, it could access unauthorized files.

## Proposed Solutions

### Solution A: Validate and Anchor (Recommended)
1. Apply `TradingViewScraperSettings.validate_run_id` to `SelectionContext.run_id` at the entry point or within the stage.
2. Use `DataLoader.ensure_safe_path()` to verify `run_data_dir` is within `summaries_runs_dir`.

**Pros:**
- Robust security.
- Reuses existing validation logic.

**Cons:**
- None.

**Effort:** Small

## Recommended Action
Implement Solution A. Validate `run_id` and anchor the path using `DataLoader.ensure_safe_path`.

## Acceptance Criteria
- [ ] `SelectionContext.run_id` is validated against the whitelist.
- [ ] Path resolution uses `ensure_safe_path` or explicit boundary checks.
- [ ] Path traversal attempts raise `ValueError`.

## Work Log
- 2026-02-05: Identified during security review by Security Sentinel.
