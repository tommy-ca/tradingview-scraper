---
status: pending
priority: p1
issue_id: "039"
tags: ['security', 'refactor']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
There are still remaining usages of `pd.read_pickle` in the codebase. Pickle is insecure and can lead to Remote Code Execution (RCE) if a malicious file is loaded. All data persistence should transition to Parquet.

## Findings
- **Issue**: Legacy code paths still rely on pickle for intermediate artifacts.
- **Impact**: Security vulnerability and potential data corruption across different Python versions.

## Proposed Solutions

### Solution A: Global Transition to Parquet
Perform a global search for `read_pickle` and `to_pickle` and replace them with `read_parquet` and `to_parquet` using `fastparquet` or `pyarrow`.

## Recommended Action
Replace all remaining pickle-based I/O with Parquet, ensuring that schemas are preserved and appropriate compression is used.

## Acceptance Criteria
- [ ] Zero instances of `pd.read_pickle` or `pickle.load` remain in the production code path.
- [ ] Data loading is verified for all affected modules.
- [ ] Parquet files are validated for performance and size parity.

## Work Log
- 2026-02-02: Issue identified as P1 finding. Created todo file.
