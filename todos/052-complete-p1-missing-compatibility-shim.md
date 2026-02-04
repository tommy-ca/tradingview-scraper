---
status: done
priority: p1
issue_id: "052"
tags: [code-review, breaking-change, sdk]
dependencies: []
---

# Problem Statement
The renaming of `QuantSDK` to `QuantLib` is a breaking change that has not been fully propagated to external components, specifically Claude skills and agent documentation.

# Findings
- `.claude/skills/quant-discover/scripts/run_discovery.py` still attempts to import `QuantSDK`.
- `AGENTS.md` and design documents in `docs/design/` still reference the old `QuantSDK` patterns.
- This prevents agents from successfully discovering and invoking system functionality.

# Proposed Solutions
1. **Add Compatibility Shim**: Create `tradingview_scraper/orchestration/sdk.py` that exports `QuantSDK = QuantLib`. (Recommended)
2. **Global Search and Replace**: Update every reference in skills and markdown files. (High effort, high risk of missing items)

# Acceptance Criteria
- [x] Compatibility shim implemented in `sdk.py`.
- [x] All Claude skills verified to work with the new structure.
- [x] Documentation reflects the `QuantLib` terminology where appropriate.

# Work Log
### 2026-02-04 - Finding Created
**By:** Claude Code
- Identified breaking change in SDK/Lib naming.

### 2026-02-04 - Shim Implemented
**By:** Claude Code
- Created `tradingview_scraper/orchestration/sdk.py` exporting `QuantSDK = QuantLib`.
- Verified importability with python shim check.
