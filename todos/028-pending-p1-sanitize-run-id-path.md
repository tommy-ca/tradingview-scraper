---
status: pending
priority: p1
issue_id: "028"
tags: ['security', 'path-traversal', 'sanitization']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
The `run_id` variable, which can be provided via user input or external configuration, is used directly in the construction of filesystem paths (e.g., `summaries_run_dir`) without proper sanitization. This poses a risk of path traversal or creation of files in unintended locations.

## Findings
- **Context**: Orchestration and logging logic where `run_id` is used to create directory structures.
- **Issue**: Lack of validation or sanitization on `run_id` before using it in `os.path.join` or similar path construction methods.
- **Impact**: Potential path traversal attacks if a malicious `run_id` (e.g., `../../etc`) is provided.

## Proposed Solutions

### Solution A: Whitelist Validation (Recommended)
Implement strict validation for `run_id` using a regular expression that only allows safe characters (e.g., alphanumeric, underscores, and hyphens).

```python
import re

def sanitize_run_id(run_id: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_\-]+$", run_id):
        raise ValueError(f"Invalid run_id: {run_id}. Only alphanumeric, underscores, and hyphens are allowed.")
    return run_id
```

### Solution B: Path Anchoring
Ensure that the final constructed path is always a subdirectory of the intended base directory using `os.path.abspath` and checking the common prefix.

## Recommended Action
Implement a sanitization function using whitelist validation for `run_id` and apply it at the point where `run_id` is first received or used for path construction.

## Acceptance Criteria
- [ ] `run_id` is validated against a safe whitelist (regex).
- [ ] Attempts to use a `run_id` with directory traversal characters (e.g., `/`, `\`, `..`) are rejected with an error.
- [ ] Unit tests verify both safe and unsafe `run_id` inputs.

## Work Log
- 2026-02-02: Issue identified during P1 security audit. Created todo file.
