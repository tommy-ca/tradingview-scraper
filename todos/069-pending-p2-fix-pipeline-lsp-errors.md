---
status: pending
priority: p2
issue_id: "069"
tags: [quality, type-checking, lsp, pipeline]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
Static analysis (LSP) has identified an error in `tradingview_scraper/pipelines/selection/base.py` regarding the `pandera` module.

## Findings
- **Location**: `tradingview_scraper/pipelines/selection/base.py`
- **Errors**:
    - `"errors" is not a known attribute of module "pandera"`

## Proposed Solutions

### Solution A: Verify Import (Recommended)
- Check how `pandera.errors` is accessed. It might need an explicit import `from pandera import errors` or `import pandera.errors`.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [ ] LSP error resolved in `pipelines/selection/base.py`.

## Work Log
- 2026-02-05: Identified during code review.
