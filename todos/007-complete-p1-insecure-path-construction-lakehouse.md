---
status: complete
priority: p1
issue_id: 007
tags: ['security', 'critical', 'traversal', 'storage']
dependencies: []
---

## Problem Statement
The `LakehouseStorage` class in `tradingview_scraper/symbols/stream/lakehouse.py` contains an **Insecure Path Construction** vulnerability in its internal `_get_path` method. This method lacks sanitization for the `symbol` and `interval` parameters, which are used to build filesystem paths.

## Findings
- **File**: `tradingview_scraper/symbols/stream/lakehouse.py`
- **Location**: Lines 27-29
- **Evidence**:
  ```python
  def _get_path(self, symbol: str, interval: str) -> str:
      safe_symbol = symbol.replace(":", "_")
      return os.path.join(self.base_path, f"{safe_symbol}_{interval}.parquet")
  ```
- **Root Cause**: Reliance on `replace(":", "_")` is insufficient to prevent path traversal. The `os.path.join` call will resolve paths starting from the last absolute path component or allow `..` to escape `base_path`.
- **Risk**: Since `LakehouseStorage` is used for saving, loading, and auditing data, this vulnerability could lead to arbitrary file reads, writes, or deletions depending on the calling context.

## Proposed Solutions

### Solution A: Centralized Path Sanitization
Refactor `_get_path` to use a robust sanitization function that rejects any input containing path separators or traversal sequences.

### Solution B: Secure Path Utility
Introduce a shared `SecurityUtils.get_safe_path(base, *parts)` that ensures the final path is contained within `base`.

## Acceptance Criteria
- [ ] Refactor `LakehouseStorage._get_path` to use strict validation or path anchoring.
- [ ] Ensure both `symbol` and `interval` are sanitized.
- [ ] Add regression tests demonstrating that traversal attempts are blocked.
- [ ] Verify no regression in existing storage operations (save/load/gap-detect).

## Work Log
- 2026-02-01: Vulnerability identified in core storage layer during security review.
