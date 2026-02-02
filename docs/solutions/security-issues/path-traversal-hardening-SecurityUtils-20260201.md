---
category: security-issues
tags: [security, path-traversal, sanitization, hardening]
module: shared-utils
symptoms: [arbitrary-file-read, arbitrary-file-deletion]
---

# Path Traversal Hardening via SecurityUtils

## Problem
Naive symbol sanitization in `IngestionService`, `BackfillService`, and `LakehouseStorage` relied on simple string replacement (`replace(":", "_")`). This approach was insufficient to prevent path traversal attacks or absolute path injection, creating a risk of arbitrary file reads or deletions if symbol names were manipulated (e.g., from a compromised `candidates.json`).

## Root Cause
The previous logic only addressed Windows-incompatible characters (colons) but did not block:
1.  Directory traversal sequences (`..`).
2.  Absolute paths (starting with `/` or `\`).
3.  Malicious characters that could be used in other contexts.

Since the resulting strings were used directly in `Path` joins without anchoring, an attacker could escape the intended data directory.

## Solution
Implemented a centralized `SecurityUtils` class in `tradingview_scraper/utils/security.py` to enforce strict sanitization and path anchoring.

### 1. Strict Regex Validation
A whitelist-based regex (`^[a-zA-Z0-9_\-.:]+$`) ensures symbols only contain alphanumeric characters, underscores, dashes, dots, and colons. Any symbol failing this check is rejected immediately.

### 2. Guard against Traversal Patterns
Explicit checks for `..` and leading slashes provide a secondary defense layer even if the regex were modified.

### 3. Absolute Path Anchoring
The `SecurityUtils.get_safe_path()` method uses `Path.resolve()` to normalize both the base directory and the final path. It explicitly verifies that the resolved target path is a child of the resolved base directory using `is_relative_to()` (or prefix matching as a fallback).

```python
# target_path is anchored to base_path
if not target_path.is_relative_to(base_path):
    raise ValueError(f"Path traversal attempt detected: {symbol}")
```

## Verification Results
- **Unit Tests**: `tests/test_security_hardening.py` confirms that payloads like `../../../etc/passwd` and `/etc/passwd` are blocked with `ValueError`.
- **Service Integration**: `IngestionService`, `BackfillService`, and `LakehouseStorage` have been refactored to use `SecurityUtils.get_safe_path()` for all filesystem operations involving symbol-based filenames.

## Related Issues
- `todos/007-complete-p1-insecure-path-construction-lakehouse.md`
- `todos/006-complete-p1-read-only-path-traversal-backfill.md`
