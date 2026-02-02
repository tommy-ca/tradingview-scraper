---
category: runtime-errors
tags: [concurrency, ray, contextvars, settings, thread-safety]
module: orchestration
symptoms: [settings-leakage, race-conditions, non-deterministic-behavior]
---

# Thread-Safe Configuration in BacktestEngine

## Problem
Parallel **Ray** tasks were experiencing unpredictable behavior and "settings leakage" where one task's configuration (e.g., `TV_PROFILE` or `TV_RUN_ID`) would overwrite another's. This occurred because multiple parallel execution paths were competing for the same global singleton configuration.

## Root Cause
The system relied on a **Singleton Settings Pattern** with global side effects:
1. `get_settings()` returned a process-wide singleton cached via `@lru_cache`.
2. Brittle "hacks" like `os.environ` mutation and `get_settings.cache_clear()` were used to switch contexts for sub-sleeves or sub-profiles.
3. In a multi-threaded or async-task environment (like Ray actors), these global mutations caused race conditions.

## Solution
The configuration layer was refactored to use **Context-Local Storage** and **Explicit Dependency Injection (DI)**:

### 1. ContextVars-Aware Settings
Refactored `get_settings()` in `tradingview_scraper/settings.py` to prioritize a `ContextVar`. This ensures each execution flow (thread/task) has its own isolated view of the configuration.

```python
_SETTINGS_CTX: ContextVar[Optional[TradingViewScraperSettings]] = ContextVar("settings_ctx", default=None)

def get_settings() -> TradingViewScraperSettings:
    if (ctx_settings := _SETTINGS_CTX.get()) is not None:
        return ctx_settings
    return _get_cached_base_settings()
```

### 2. Explicit Dependency Injection
Modified the `BacktestEngine` constructor to accept an optional `settings` object. This allows engines to be instantiated with fixed, immutable configurations, bypassing global lookups entirely.

### 3. Removal of Global Mutations
Eliminated all `cache_clear()` calls and `os.environ` hacks from the runtime logic.

## Impact
- **Deterministic Parallelism**: 100% elimination of race conditions in recursive meta-portfolio simulations.
- **Improved Testability**: Engines can now be tested with specific configurations injected without affecting the global state.

## Related Issues
- `todos/016-pending-p1-thread-safety-global-state.md`
