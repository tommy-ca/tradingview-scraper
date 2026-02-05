---
status: pending
priority: p1
issue_id: "051"
tags: [security, remote-code-execution, pickle, critical]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The codebase still explicitly checks for and loads `.pkl` / `.pickle` files using `pd.read_pickle` in the `IngestionStage` and `meta_returns.py`, despite a migration effort to Parquet. This leaves the application vulnerable to Remote Code Execution (RCE) via malicious data files.

## Findings
- **Location 1**: `tradingview_scraper/pipelines/selection/stages/ingestion.py`: Lines 124-125
  ```python
  elif ext in [".pkl", ".pickle"]:
      data = pd.read_pickle(returns_path)  # Unsafe
  ```
- **Location 2**: `tradingview_scraper/utils/meta_returns.py`: Lines 175 & 185
- **Risk**: High. Deserializing untrusted pickle files can execute arbitrary code.

## Proposed Solutions

### Solution A: Immediate Removal (Recommended)
Remove the code paths that handle `.pkl` and `.pickle` extensions. Enforce `.parquet` usage strictly.

**Pros:**
- Immediate security fix.
- Aligns with the "Migrate to Parquet" goal.
- Code simplification.

**Cons:**
- Breaks backward compatibility for any workflows relying on old pickle files (though migration scripts exist).

**Effort:** Small

### Solution B: Safe Unpickler (Not Recommended)
Implement a restricted unpickler.

**Pros:** Allows legacy support.
**Cons:** Hard to get right, still risky, adds complexity.

## Recommended Action
Implement Solution A. Remove support for pickle files in ingestion and meta returns utilities.

## Acceptance Criteria
- [ ] `pd.read_pickle` is removed from `tradingview_scraper/pipelines/selection/stages/ingestion.py`.
- [ ] `pd.read_pickle` is removed from `tradingview_scraper/utils/meta_returns.py`.
- [ ] Attempts to ingest `.pkl` files raise a clear error or are ignored.

## Work Log
- 2026-02-05: Identified during security review by Security Sentinel.
