---
status: complete
priority: p2
issue_id: "011"
tags: [quality, security]
dependencies: []
---

# Redundant Sanitization in ingest_data.py

The `IngestionService` in `scripts/services/ingest_data.py` contains redundant and unstructured sanitization logic that checks for characters already blocked by a strict regex.

## Problem Statement

- The `_sanitize_symbol` method uses a strict regex `r"^[a-zA-Z0-9_\-.:]+$"` that only allows alphanumeric characters and a specific set of symbols.
- Subsequent manual checks for `..`, `/`, and `\` are redundant because the regex already blocks `/` and `\`, and while it allows `.`, the `..` check is separate but slightly overlapping in intent with the regex.
- `_get_parquet_path` also uses `.resolve()` and a prefix check, which is the correct way to prevent path traversal, making the earlier manual character checks even more redundant.
- Redundant security checks can lead to a false sense of security or make the code harder to read and maintain.

## Findings

- **File**: `scripts/services/ingest_data.py`
- **Method**: `_sanitize_symbol` (lines 39-51)
    - Line 41: Regex `r"^[a-zA-Z0-9_\-.:]+$"` blocks `/` and `\`.
    - Line 49: `if ".." in safe_sym or safe_sym.startswith("/") or safe_sym.startswith("\\")` is impossible to trigger for `/` and `\` if line 41 passes.
- **Method**: `_get_parquet_path` (lines 53-62)
    - Uses `.resolve()` and `.startswith()` (line 59) which is the authoritative way to verify path containment.

## Proposed Solutions

### Option 1: Clean Up Redundant Checks
**Approach:** Simplify `_sanitize_symbol` to only use the regex and character replacement (for `:` to `_`). Rely on `_get_parquet_path`'s `.resolve()` and prefix check for the actual path traversal protection.

**Pros:**
- Cleaner, more idiomatic code.
- No change in security posture (prefix check is the strongest guard).

**Cons:**
- None.

**Effort:** 1 hour
**Risk:** Very Low

## Recommended Action

**To be filled during triage.** Consolidate all path-safety logic into `_get_parquet_path` and keep `_sanitize_symbol` focused only on string transformation.

## Technical Details

**Affected files:**
- `scripts/services/ingest_data.py:39` - `_sanitize_symbol`
- `scripts/services/ingest_data.py:53` - `_get_parquet_path`

## Acceptance Criteria

- [ ] Redundant character checks (`/`, `\`) removed from `_sanitize_symbol`.
- [ ] Path traversal protection unified around `.resolve()` and prefix validation.
- [ ] Unit tests for symbol ingestion still pass.
- [ ] Malicious symbols (e.g., `../../../etc/passwd`) are still correctly rejected.

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Analyzed `scripts/services/ingest_data.py` for redundant sanitization.
- Verified that regex blocks characters that are later checked manually.
- Created todo entry 011.

## Notes

- This cleanup follows the "DRY" principle and improves the clarity of the security model.
