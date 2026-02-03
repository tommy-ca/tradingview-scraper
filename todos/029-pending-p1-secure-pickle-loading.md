---
status: pending
priority: p1
issue_id: "029"
tags: ['security', 'deserialization', 'data-loading']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
`BacktestEngine.load_data` uses `pd.read_pickle` on paths that may be influenced by external input. Loading pickle files from untrusted sources is insecure as it can lead to arbitrary code execution.

## Findings
- **Context**: `BacktestEngine.load_data` method.
- **Issue**: Use of `pickle` (via `pandas.read_pickle`) for data persistence/loading.
- **Impact**: Security vulnerability where a malicious pickle file could execute arbitrary code on the system. Additionally, pickle files are version-dependent and less efficient than modern formats like Parquet.

## Proposed Solutions

### Solution A: Switch to Parquet (Recommended)
Migrate the data persistence layer from Pickle to Parquet. Parquet is secure, efficient, and widely supported.

```python
# Instead of:
# df = pd.read_pickle(path)
# Use:
df = pd.read_parquet(path)
```

### Solution B: Path Anchoring and Verification
If Pickle must be used, ensure that the files being loaded are strictly anchored within a trusted directory and verify their integrity before loading. However, this does not eliminate the inherent risks of Pickle.

## Recommended Action
Replace `pd.read_pickle` with `pd.read_parquet` in `BacktestEngine.load_data` and update the corresponding save logic to use `to_parquet`. Ensure that the storage directory is strictly controlled.

## Acceptance Criteria
- [ ] `pd.read_pickle` replaced with `pd.read_parquet` in `BacktestEngine.load_data`.
- [ ] Data saving logic updated to use Parquet.
- [ ] Existing data files migrated or handled gracefully.
- [ ] Unit tests verify that data can be saved and loaded securely.

## Work Log
- 2026-02-02: Issue identified during P1 security audit. Created todo file.
