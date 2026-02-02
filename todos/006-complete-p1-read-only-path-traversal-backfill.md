---
status: complete
priority: p1
issue_id: 006
tags: ['security', 'critical', 'traversal', 'backfill']
dependencies: []
---

## Problem Statement
The `BackfillService.run` method in `scripts/services/backfill_features.py` is vulnerable to a **Read-Only Path Traversal** attack. The `symbol` value, which can be loaded from an external `candidates.json` file, is used to construct file paths without validation.

## Findings
- **File**: `scripts/services/backfill_features.py`
- **Location**: Line 81-82
- **Evidence**:
  ```python
  safe_sym = symbol.replace(":", "_")
  file_path = self.lakehouse_dir / f"{safe_sym}_1d.parquet"
  ```
- **Root Cause**: The code assumes `symbol` only contains safe characters after replacing `:` with `_`. However, if `symbol` contains path traversal sequences like `../../`, `file_path` can resolve to a location outside the intended `lakehouse_dir`.
- **Risk**: An attacker providing a malicious `candidates.json` could potentially force the script to read and process arbitrary Parquet files from the filesystem.

## Proposed Solutions

### Solution A: Symbol Validation (Recommended)
Implement a strict validation check for symbols before path construction. Symbols should match a predefined pattern (e.g., `^[A-Z0-9_:]+$`).

### Solution B: Path Anchoring
Use `Path.resolve()` and verify that the resulting `file_path` is a child of `self.lakehouse_dir`.

## Acceptance Criteria
- [ ] Implement `_validate_symbol` or similar utility to ensure symbol sanity.
- [ ] Ensure `file_path` is strictly within `lakehouse_dir`.
- [ ] Add unit tests for symbols with traversal patterns (e.g., `../../etc/passwd`).
- [ ] Verify that the script continues to function for valid symbols like `BINANCE:BTCUSDT`.

## Work Log
- 2026-02-01: Issue identified during security audit of backfill logic.
