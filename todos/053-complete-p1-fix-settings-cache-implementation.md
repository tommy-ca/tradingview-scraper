---
status: complete
priority: p1
issue_id: "053"
tags: [architecture, bug, performance, settings]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
The `_get_cached_base_settings` function in `settings.py` claims to cache settings but creates a new instance on every call because it lacks the caching implementation (or uses it incorrectly in the new code).

## Findings
- **Location**: `tradingview_scraper/settings.py`: Lines 466-468
- **Evidence**:
  ```python
  def _get_cached_base_settings() -> TradingViewScraperSettings:
      """Loads default settings once and caches them."""
      return TradingViewScraperSettings()  # <--- NEW INSTANCE EVERY TIME
  ```
- **Impact**: Significant performance degradation due to repeated I/O (reading `.env`, `manifest.json`) on every settings access.

## Proposed Solutions

### Solution A: Global Variable Caching (Recommended)
Use a global variable to store the singleton instance.

```python
_GlobalSettingsCache = None
def _get_cached_base_settings():
    global _GlobalSettingsCache
    if _GlobalSettingsCache is None:
        _GlobalSettingsCache = TradingViewScraperSettings()
    return _GlobalSettingsCache
```

### Solution B: Re-add lru_cache
Re-apply `@lru_cache` but ensure it works correctly with the no-argument function and can be cleared if needed.

**Pros:** Simple standard library solution.
**Cons:** We just removed it to fix a bug, need to ensure `cache_clear` is exposed and works.

## Recommended Action
Implement Solution A for explicit control and clarity, or correctly implement Solution B if `cache_clear` was the only issue. Given the recent changes, a manual singleton pattern is often clearer.

## Acceptance Criteria
- [x] `_get_cached_base_settings` returns the same instance on subsequent calls.
- [x] `clear_settings_cache` correctly resets the instance.
- [x] Performance test confirms `.env` is read only once.

## Work Log
- 2026-02-05: Identified during pattern review.
- 2026-02-05: Implemented Solution A using `_GlobalSettingsCache`. Added unit test `tests/test_settings_cache.py` which confirmed singleton behavior and cache clearing.
