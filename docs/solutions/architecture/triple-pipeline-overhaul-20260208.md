---
module: System
date: 2026-02-08
problem_type: logic_error
component: service_object
symptoms:
  - "Inconsistent developer experience across modular pillars (Selection vs Allocation)"
  - "Logic duplication between BacktestEngine and modular pipelines (split-brain)"
  - "Memory overflow (OOM) on driver nodes during large matrix consolidation"
  - "Hardcoded risk constraints embedded in the simulation orchestrator"
root_cause: logic_error
resolution_type: code_fix
severity: high
tags: [architecture, refactor, triple-pipeline, performance, decoupling, ray]
---

# Architecture: Triple Pipeline Overhaul 2026-02-08

## Problem
The quantitative platform reached a point of "architectural debt" as it transitioned from a script-based scraper to an institutional multi-pillar system. Pillar 1 (Discovery) and Pillar 2 (Selection) were modernized into modular pipelines, but Pillar 3 (Allocation) remained legacy code embedded within the `BacktestEngine` god object. This led to logic duplication, inability to parallelize optimization tasks, and performance bottlenecks in data synthesis and consolidation.

## Environment
- Module: System
- Affected Components: `BacktestEngine`, `SelectionPipeline`, `AllocationPipeline`, `synthesis.py`, `backfill_features.py`
- Date: 2026-02-08

## Symptoms
- **Split-Brain Logic**: The `BacktestEngine` manually managed selection logic while a dedicated `SelectionPipeline` existed, leading to risk of logic drift.
- **Pillar 3 Asymmetry**: Pillar 3 stages (Optimization, Simulation) were plain classes lacking the `@validate_io` and `StageRegistry` benefits of Pillar 1/2.
- **OOM Crashes**: Consolidating features for >5,000 symbols caused driver nodes to exceed memory limits (pd.concat bottleneck).
- **Python Loop Bottlenecks**: Momentum synthesis used `.rolling().apply()`, which was too slow for large-scale backtesting.

## What Didn't Work
- **Attempted Solution 1:** Maintaining legacy selection logic in `BacktestEngine` with feature flags.
- **Why it failed:** Increased maintenance cost and failed to leverage the standardized audit trail of the modular pipeline.
- **Attempted Solution 2:** Simple `pd.concat` for all symbols in backfill services.
- **Why it failed:** Caused driver nodes to run out of memory when processing large histories and high-density universes.

## Solution
A comprehensive structural overhaul was executed to complete the "Triple-Pipeline" vision and harden the numerical core.

### 1. Modularization of Pillar 3 (Allocation)
Decoupled Pillar 3 logic from `BacktestEngine` into a formal `AllocationPipeline`.
- **Standardization**: `OptimizationStage` and `SimulationStage` now inherit from `BasePipelineStage`.
- **Parallelization**: Implemented `AllocationContext.merge()` to support distributed optimization profiles on Ray clusters.

### 2. Engine Unification
The `BacktestEngine` was refactored from an "All-in-One" orchestrator into a lean "Coordinator."
- **Delegation**: Alpha selection is now delegated entirely to the `SelectionPipeline`.
- **Risk Layer Purity**: Hardcoded diversity constraints (25% caps) were moved to a dedicated `risk/constraints.py` module with configurable institutional settings.

### 3. Numerical Hardening & Vectorization
- **Momentum Speedup**: Vectorized momentum synthesis using a log-sum-exp approach, achieving a ~100x speedup over Python loops.
- **Memory Guardrails**: Implemented incremental concatenation in `backfill_features.py` to bound driver memory usage during large-scale ingestion.

### 4. Simplicity Sweep
- **Ruthless Purge**: Deleted ~1,850 lines of redundant code, legacy orchestrators, and scripts in `scripts/archive/`.
- **Security**: Removed residual insecure `pickle` loaders in favor of Parquet/JSON.

**Code changes**:
```python
# Before (Inefficient Synthesis):
def rolling_momentum(rets, window):
    return rets.rolling(window).apply(lambda x: (1 + x).prod() - 1)

# After (Vectorized Log-Sum):
def rolling_momentum(rets, window):
    log_rets = np.log1p(rets).cumsum()
    return np.exp(log_rets - log_rets.shift(window)) - 1
```

```python
# Before (God Object Engine):
class BacktestEngine:
    def _execute_selection(self, ...):
        # ... legacy selection logic ...

# After (Lean Coordinator):
class BacktestEngine:
    def _run_window_step(self, ...):
        # Delegates to the specialized pipeline
        selection_ctx = SelectionPipeline.run_with_data(...)
        # ...
```

## Why This Works
1.  **Single Responsibility Principle**: The engine now only coordinates simulation flow, while pipelines manage logic for selection and allocation.
2.  **Architectural Symmetry**: All three pillars now share the same modular foundation, simplifying developer onboarding and stage reuse.
3.  **Numerical Stability**: Log-sum vectorization is not only faster but numerically more stable for long-term return compounding.
4.  **Scalability**: Distributed `merge()` and incremental concatenation allow the platform to scale to 10k+ symbols without driver-side bottlenecks.

## Prevention
- **Pillar Enforcement**: Any new logic related to Alpha or Risk MUST be implemented as a `BasePipelineStage`.
- **God Object Guard**: Regularly audit `BacktestEngine` for logic leakage; if a method exceeds 50 lines of domain logic, it should be extracted to a pipeline or utility.
- **Vectorization First**: Reject any PR that uses `.apply()` or Python loops in the numerical path (synthesis, filtering, optimization).

## Related Issues
- See also: [dataops-core-pillar-hardening-20260207.md](./dataops-core-pillar-hardening-20260207.md)
- See also: [god-method-refactor-BacktestEngine-20260201.md](../logic-errors/god-method-refactor-BacktestEngine-20260201.md)
- Similar to: [thread-safe-config-BacktestEngine-20260202.md](../runtime-errors/thread-safe-config-BacktestEngine-20260202.md)

No other related issues documented yet.
