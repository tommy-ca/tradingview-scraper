---
title: "refactor: Harden BacktestEngine and optimize quant utilities (Deepened)"
type: refactor
date: 2026-02-02
status: deepened-draft
---

# refactor: Harden BacktestEngine and optimize quant utilities (Deepened)

## 1. Executive Summary
This deepened plan provides a high-fidelity roadmap for refactoring the `BacktestEngine` and associated utilities. It enforces strict Python 3.10+ standards, numerical stability via memory-contiguity guards, and thread-safe orchestration using `ContextVars`.

## 2. Strict Python Standards (Python 3.10+)
- **Type Hinting**: Elimination of `typing.Union` and `typing.Optional` in favor of the `|` operator.
- **Collection Types**: Exclusive use of built-in generic types (`list`, `dict`, `tuple`) instead of `typing` equivalents.
- **Deferred Evaluation**: Utilization of `from __future__ import annotations` to support forward references and minimize runtime overhead.
- **Docstrings**: Adoption of the "Args/Returns/Audit" pattern for all public and internal methods.

## 3. Numba JIT & Numerical Hardening
### 3.1 Optimized Signatures
Every JIT-compiled function must have an explicit signature to ensure deterministic compilation and avoid object-mode fallback.
```python
from numba import njit, float64, int64

@njit(float64(float64[:], int32[:], float64[:], int64, int64), cache=True, fastmath=True)
def _calculate_permutation_entropy_jit(x, perm_counts, segment_buffer, order, delay):
    # Implementation ...
```

### 3.2 Memory Contiguity Guards
To prevent performance degradation or illegal memory access in JIT loops, all input arrays must be validated for contiguity.
- **Protocol**: Call `np.ascontiguousarray(x, dtype=np.float64)` at the boundary between Python and JIT code.
- **Rationale**: Ensures the C-order layout required for efficient vectorization.

### 3.3 Buffer Reuse ("Out" Parameter Pattern)
- **Elimination of Allocations**: Hot loops (e.g., `rs_analysis`, `entropy`) must accept pre-allocated buffers.
- **Stability**: Zero-filling of buffers must occur via `.fill(0)` or slicing rather than re-allocation.

## 4. Thread-Safe Orchestration (ContextVars)
### 4.1 Dependency Injection
- `BacktestEngine` must accept a `settings` object in its constructor.
- Global `get_settings()` must only be used as a fallback.

### 4.2 Context-Aware Execution
- `_SETTINGS_CTX` will be the single source of truth for the active configuration.
- **Ray Integration**: When launching remote tasks, the current `ContextVar` value must be explicitly passed and set on the worker node.
```python
def worker_task(settings_snapshot):
    set_active_settings(settings_snapshot)
    # ... execute task
```

## 5. Implementation Phases (Detailed)

### Phase 1: Numerical Foundation
- **`predictability.py`**:
    - Implement explicit signatures for all `njit` functions.
    - Add `np.ascontiguousarray` guards to all public entry points.
    - Standardize on `float64` for all mathematical calculations.

### Phase 2: Engine Refinement
- **`backtest_engine.py`**:
    - Modernize all type hints to Python 3.10+ syntax.
    - Extract `RidgeHardening` and `SanityVeto` into a `SolverGuard` class/decorator.
    - Reduce `_process_optimization_window` signature from 12+ parameters to 4 (engine_name, profile, window, test_rets).

### Phase 3: Settings & Discoverability
- **`settings.py`**:
    - Implement `inspect_active_settings()` for agent transparency.
    - Ensure `TradingViewScraperSettings` supports `clone(**overrides)` for easy context switching.

## 6. Verification Criteria
- [ ] `pytest` passes with `numba.config.DISABLE_JIT = 0`.
- [ ] `numba` performance benchmark shows < 5% variance across 1000 iterations (GC stability).
- [ ] Thread-safety verified via concurrent `BacktestEngine` runs with conflicting profiles.
- [ ] All code passes `ruff` / `mypy` with strict settings.
