---
status: pending
priority: p3
issue_id: "014"
tags: ['architecture', 'config', 'manifest']
dependencies: []
created_at: 2026-02-01
---

## Problem Statement
The system currently infers strategy types (e.g., trend_following, mean_reversion) using "magic strings" and pattern matching against profile names. This approach is fragile, hard to extend, and hides configuration details from the `manifest.json`, which is intended to be the single source of truth for run reproducibility.

## Findings
- **File**: `tradingview_scraper/orchestration/strategies.py`
- **Location**: `StrategyFactory.infer_strategy`
- **Evidence**:
  ```python
  p_name = profile_name.lower()
  if "mean_rev" in p_name or "meanrev" in p_name:
      return "mean_reversion"
  elif "breakout" in p_name:
      return "breakout"
  ```
- **Context**: Relying on naming conventions for logic selection violates the principle of explicit configuration. It makes it impossible to run a "trend_following" strategy using a profile named "experimental_alpha_v1" without code changes or explicit overrides.

## Proposed Solutions

### Solution A: Explicit Manifest Strategy (Recommended)
Add a `strategy` field to the `profile` schema in `manifest.json`. Modify `StrategyFactory` to read this field directly. If missing, it can fallback to a default or the existing legacy inference (with a deprecation warning).

### Solution B: Strategy Registry
Implement a decorator-based registry for strategies, allowing them to be registered with unique IDs that match the manifest configuration. This improves decoupling between the orchestrator and individual strategy implementations.

## Recommended Action
Update `configs/manifest.json` schema to include an explicit `strategy` key for each profile. Refactor `StrategyFactory` to prioritize this key and move away from name-based inference.

## Acceptance Criteria
- [ ] `manifest.json` schema updated with `strategy` field.
- [ ] `StrategyFactory.infer_strategy` prioritizes manifest configuration.
- [ ] Legacy name-based inference is logged as deprecated.
- [ ] Unit tests verify strategy selection from manifest.
- [ ] All production profiles in `manifest.json` are updated with explicit strategy types.

## Work Log
- 2026-02-01: Issue identified during P3 findings review. Created todo file.
