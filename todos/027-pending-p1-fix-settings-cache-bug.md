---
status: pending
priority: p1
issue_id: "027"
tags: ['bug', 'settings', 'cache']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
The function `_get_cached_base_settings` uses `@lru_cache` on a zero-argument function. This effectively freezes the settings after the first call, preventing any runtime overrides from taking effect in subsequent calls or different contexts within the same process.

## Findings
- **Context**: `TradingViewScraperSettings` or similar settings module.
- **Issue**: `@lru_cache` without arguments on a function that returns a global or base configuration object.
- **Impact**: Environment variables or dynamic overrides set after the first call to this function are ignored, leading to stale configuration and difficulty in testing different scenarios.

## Proposed Solutions

### Solution A: Remove @lru_cache (Recommended)
Remove the `@lru_cache` decorator if the overhead of re-parsing or fetching settings is negligible (which it usually is for local settings).

### Solution B: Add Cache Clearing Mechanism
Keep the cache but expose a way to clear it (e.g., `_get_cached_base_settings.cache_clear()`) when settings need to be refreshed.

### Solution C: Replace with a Property or Singleton
Use a more standard singleton pattern or a property that explicitly handles the lifecycle of the settings object.

## Recommended Action
Remove `@lru_cache` from `_get_cached_base_settings` to ensure that settings are always fresh and can be overridden by environment variables or runtime configuration changes.

## Acceptance Criteria
- [ ] `@lru_cache` removed from `_get_cached_base_settings`.
- [ ] Unit tests verify that settings can be updated/overridden between calls.
- [ ] No regression in performance for settings access.

## Work Log
- 2026-02-02: Issue identified during P1 settings audit. Created todo file.
