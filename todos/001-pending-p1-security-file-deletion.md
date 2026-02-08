---
status: pending
priority: p1
issue_id: 001
tags: ['security', 'critical', 'ingestion']
dependencies: []
created_at: 2026-01-29
---

## Problem Statement
The `scripts/services/ingest_data.py` script contains a **Critical Arbitrary File Deletion Vulnerability**. The `symbol` input is used to construct a file path without sufficient sanitization. If a malicious or malformed symbol (e.g., containing `../`) is processed, the system could delete arbitrary files on the host machine when the "toxic data" cleanup logic triggers.

## Findings
- **File**: `scripts/services/ingest_data.py`
- **Location**: Lines 134-150
- **Evidence**:
  ```python
  safe_sym = symbol.replace(":", "_")  # Insufficient sanitization
  p_path = self.lakehouse_dir / f"{safe_sym}_1d.parquet"
  # ...
  if is_toxic_ret or is_toxic_vol or is_stalled:
      os.remove(p_path)  # Critical: Deletes file at potentially attacker-controlled path
  ```
- **Risk**: High. Could lead to system compromise or data loss.

## Proposed Solutions

### Solution A: Strict Allowlist (Recommended)
Validate the symbol against a strict regex (e.g., `^[a-zA-Z0-9_\-.]+$`) before use. Raise `ValueError` if invalid.

### Solution B: `os.path.basename`
Strip directory components using `os.path.basename(symbol)`. This prevents traversal but might result in collisions or confusing filenames if the input was intended to be hierarchical (which it shouldn't be).

## Technical Details
- Modify `IngestService` class.
- Add `_sanitize_symbol` helper method.
- Apply sanitization before *any* file operation.

## Acceptance Criteria
- [ ] `_sanitize_symbol` method implemented with regex validation.
- [ ] Unit test added attempting to ingest a symbol with `../`.
- [ ] Unit test confirming `ValueError` is raised for invalid symbols.
- [ ] Verify `os.remove` is never called on unsanitized paths.

## Work Log
- 2026-01-29: Issue identified by Security Sentinel agent.
