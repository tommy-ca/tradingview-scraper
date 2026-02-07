---
status: complete
priority: p1
issue_id: "090"
tags: [security, remote-code-execution, critical]
dependencies: []
---

# Incomplete Pickle Removal in DataLoader

## Problem Statement
The `DataLoader` still contains multiple calls to `pd.read_pickle`, maintaining a Remote Code Execution (RCE) vector in the core data ingestion layer. Despite the migration to Parquet, these legacy paths were not fully removed.

## Findings
- **Location**: `tradingview_scraper/data/loader.py:192, 215, 251`
- **Risk**: High. If the storage environment (S3/Local) is compromised, malicious pickle files could execute arbitrary code on the runner.
- **Evidence**: `pd.read_pickle` is used as a fallback for returns and stats.

## Proposed Solutions

### Solution A: Complete Cutover (Recommended)
Remove all `read_pickle` calls. If a parquet file is missing, the loader should either fail with a clear error or trigger an on-the-fly migration if safe.

**Pros**: Eliminates RCE risk.
**Cons**: Might break old runs that haven't been migrated.

## Recommended Action
Implement Solution A. Enforce Parquet/JSON strictly in `DataLoader`.

## Acceptance Criteria
- [x] `pd.read_pickle` is removed from `tradingview_scraper/data/loader.py`.
- [x] `pickle` import removed.
- [x] Loader raises `FileNotFoundError` or `DataContractViolation` if parquet missing.

## Work Log
- 2026-02-07: Identified during security review.
- 2026-02-08: Removed all residual pickle paths and enforced Parquet/JSON.
