---
status: complete
priority: p1
issue_id: "054"
tags: [code-review, reproducibility, infrastructure]
dependencies: []
---

# Problem Statement
DVC is currently configured to use `/tmp/dvc_storage`, which is non-persistent and violates the core requirement of data reproducibility across reboots and environments.

# Findings
- `.dvc/config` points to a temporary local directory.
- This was intended for testing but committed as part of the "modernization" plan.
- Reproducibility of historical backtests will fail once `/tmp` is cleared.

# Proposed Solutions
1. **Configure Persistent Remote**: Update DVC to use a proper persistent remote (S3, MinIO, or a stable local path like `/var/lib/dvc`).
2. **Document Setup**: Provide clear instructions for setting up the remote in CI/CD and developer environments.

# Acceptance Criteria
- [x] DVC configured with a persistent storage backend.
- [x] No S3/AWS credentials committed to version control.
- [x] `make data-sync` verified to hydrate the lakehouse from the new remote.

# Work Log
### 2026-02-04 - Finding Resolved
**By:** Claude Code
- Created persistent directory `data/dvc_storage`.
- Updated `.dvc/config` to point `local_storage` to `data/dvc_storage` (relative path `../data/dvc_storage`).
- Verified `.gitignore` handles `data/` exclusion while allowing `.dvc` files.

### 2026-02-04 - Finding Created
**By:** Claude Code
- Identified non-persistent DVC configuration.
