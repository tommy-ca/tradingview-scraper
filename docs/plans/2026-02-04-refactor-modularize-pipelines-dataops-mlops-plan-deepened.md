---
title: "refactor: Modularize Data and Alpha Pipelines with Modern DataOps/MLOps Stack"
type: refactor
date: 2026-02-04
---

# refactor: Modularize Data and Alpha Pipelines with Modern DataOps/MLOps Stack

## Enhancement Summary

**Deepened on:** 2026-02-06
**Sections enhanced:** 6
**Research agents used:** security-sentinel, performance-oracle, architecture-strategist, pattern-recognition-specialist, data-integrity-guardian, code-simplicity-reviewer, framework-docs-researcher, best-practices-researcher

### Key Improvements
1.  **Architecture Hardening**: Decoupled core library logic from orchestration engines (Engine-Agnostic Library/Flow Split) to prevent "God Task" anti-patterns.
2.  **Performance Optimization**: Integrated the "Ray Object Store Reference Pattern" and "JIT Out-Parameter Synergy" to eliminate serialization bottlenecks in distributed execution.
3.  **Security & Integrity**: Implemented "Artifact Hardening" for MLflow and "Temporal-Aware Validation" for Pandera to handle multi-asset calendars and prevent data corruption.
4.  **Simplified Tracking**: Flattened MLflow hierarchy (Single Run with Tags) and streamlined Validation (Filter & Log) to reduce operational overhead.
5.  **Escape Hatch**: The library layer (`StageRegistry`) remains fully executable via simple Python scripts, ensuring independence from the Orchestrator.

### New Considerations Discovered
-   **ThreadSafeConfig Pattern**: Essential for stable distributed worker initialization on Ray nodes.
-   **Pydantic Migration**: Mandated replacement of `TypedDict` with Pydantic Models for runtime type safety.
-   **Single Source of Truth**: `audit.jsonl` remains the primary forensic ledger; MLflow acts as the visualization view.

---

## Overview

This plan outlines the systematic modularization of the quantitative data and alpha (selection) pipelines using **Approach A: The Majestic Orchestrator**. We will integrate **Prefect** for orchestration, **MLflow** for experiment tracking, and **Pandera** for data contract enforcement. This transformation will move the platform from a custom sequential orchestrator to a production-grade MLOps ecosystem while adhering to SOLID, KISS, and YAGNI principles.

### Research Insights

**Best Practices:**
- **Majestic Monolith vs Micro-Services**: Keep the quant library unified; use Prefect purely for DAG routing and retry logic.
- **Versioned Everything**: Every run must log the `RUN_ID`, `git_commit_hash`, and a schema-validated `manifest.json`.

**Performance Considerations:**
- **Serialization Tax**: Minimize data transfer between Prefect tasks; prefer passing IDs or Ray References over raw DataFrames.

**References:**
- https://docs.prefect.io/concepts/tasks/ (Managed Retries)
- https://mlflow.org/docs/latest/tracking.html#nested-runs (Nested Hierarchy)

---

## Proposed Solution: Approach A (The Majestic Orchestrator)

We will layer a professional DataOps stack on top of the existing `BasePipelineStage` architecture.

### Research Insights

**Implementation Details:**
```python
# Implementation of the Library/Flow Split
from prefect import task, flow

@task(retries=3, retry_delay_seconds=10)
def process_stage_task(context: SelectionContext, stage_id: str):
    # Retrieve the stateless library stage
    stage = StageRegistry.get(stage_id)
    # Execute core quant logic (Engine-Agnostic)
    return stage.execute(context)

@flow(name="Majestic Selection Pipeline")
def selection_flow(run_params: dict):
    context = SelectionContext(**run_params)
    for stage_id in ["foundation.ingest", "alpha.engineering"]:
        context = process_stage_task(context, stage_id)
```

---

## Technical Considerations

-   **Reference-First State**: To avoid IPC overhead on Ray workers, `SelectionContext` will prioritize passing `Ray.ObjectRef` or file paths for large DataFrames instead of raw values.
-   **Run ID Syncing**: We will unify Prefect `flow_run_id`, MLflow `run_id`, and `SelectionContext.run_id` at the pipeline entry gate.
-   **Temporal-Aware Validation**: Pandera schemas will be modified to allow NaNs for assets prior to their genesis date to support multi-sleeve crypto runs.
-   **Zero-Allocation Synergy**: Integration with `NumericalWorkspace` will be maintained to ensure validation steps do not introduce unnecessary memory thrashing.
-   **Type Safety**: All flow inputs and `RunData` structures will use **Pydantic Models** to ensure runtime validation at boundaries.
-   **Thread Safety**: A `ThreadSafeConfig` pattern using `ContextLocal` storage will be implemented to prevent settings leakage across Ray workers.

### Research Insights

**Performance Considerations:**
- **Ray Object Store Synergy**: Use `ray.put()` for the `ReturnsMatrix` at the start of the pipeline. Passing the reference prevents $O(N)$ serializations across worker nodes.
- **JIT Out-Parameter Synergy**: Validation logic should use pre-allocated buffers (Workspace) when performing high-frequency checks on rolling windows.

**Edge Cases:**
- **ThreadSafeConfig**: Ray workers initialization can suffer from "Settings Leakage". Use `ContextLocal` storage for platform settings.

**Implementation Details:**
```python
# Recommended Reference Pattern
def execute_distributed_ingest(huge_df: pd.DataFrame):
    import ray
    # Store once in Plasma store
    df_ref = ray.put(huge_df)
    # Pass by reference to distributed tasks
    results = [compute_alpha.remote(df_ref) for _ in range(num_workers)]
```

---

## MLflow Tracking & Registry

The platform will move from filesystem-based auditing to a centralized MLflow Tracking server.

### Research Insights

**Best Practices:**
- **Flattened Run Pattern**: Use a single MLflow run per pipeline execution. Store atom-level metrics (e.g., "BTC_Trend") as tagged metrics or consolidated artifacts to avoid database bloat.
- **Selective Logging**: Log high-cardinality metrics (per-asset) to Parquet artifacts; keep the MLflow UI clean with aggregate Sharpe/MaxDD.
- **View-Only Role**: Treat MLflow as a visualization layer for the immutable `audit.jsonl` ledger, not a parallel write target.

**Security Considerations:**
- **Artifact Hardening**: Explicitly ban `pickle` for MLflow artifacts; enforce `.parquet` for returns and `.json` for config to prevent RCE.

**Implementation Details:**
```python
# Hardened tracking pattern
with mlflow.start_run(run_name=context.run_id):
    mlflow.log_params(context.params.model_dump())  # Pydantic dump
    # Log metrics with tags instead of nested runs
    mlflow.log_metric("sharpe", 1.85, tags={"strategy": "BTC_Trend"})
```

---

## Pandera Validation Strategy (2-Tier)

We will implement a simplified 2-tier validation strategy to ensure "No Padding" and "Non-Toxic" data standards without validation paralysis.

### Research Insights

**Best Practices:**
- **Tier 1: Schema (Fast)**: Structural checks (types, column existence, simple ranges) running on Ingest. Critical for preventing crashes.
- **Tier 2: Audit (Deep)**: Semantic checks (integrity, statistical drift, history alignment) running as separate async jobs or final gates.
- **Filter & Log**: Instead of "Lazy Validation" (which aggregates errors in memory), use a "Filter & Log" strategy. Drop invalid rows/assets immediately, log the exclusion to `audit.jsonl`, and proceed with the valid subset.
- **Temporal-Aware Validation**: Schemas must handle different genesis dates (e.g., BTC vs. PEPE) without flagging valid leading NaNs.

**Performance Considerations:**
- **Avoid Validation Tax**: Strict L4 checks on every Ray task are removed. Semantic validation happens only at pillar boundaries.

**Implementation Details:**
```python
# Tier 1: Basic Hygiene Schema (Fast)
ReturnsSchema = pa.DataFrameSchema({
    "date": pa.Column(pa.DateTime),
    "symbol": pa.Column(pa.String),
    "returns": pa.Column(pa.Float, checks=pa.Check.in_range(-1.0, 5.0))
})

# Filter & Log Logic
def validate_and_filter(df, schema):
    try:
        return schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as e:
        # Log dropped symbols to audit trail
        # FIX: Access failure cases correctly
        failed_indices = e.failure_cases["index"].unique()
        logger.warning(f"Dropping {len(failed_indices)} invalid rows.")
        return df.drop(failed_indices)
```

---

## Implementation Phases

### Phase 1: Foundation & Validation (P1)
- [ ] Define global `ReturnsSchema` and `FeatureStoreSchema` in `tradingview_scraper/pipelines/contracts.py` (2-Tier Strategy).
- [ ] Implement `@validate_io` decorator in `selection/base.py` using "Filter & Log" strategy.
- [ ] Implement `MLflowTracker` utility in `tradingview_scraper/telemetry/`.
- [ ] Implement `ThreadSafeConfig` using `ContextLocal` storage for distributed workers.
- [ ] Migrate `SelectionContext` and `RunData` to strict **Pydantic Models** (replace TypedDict).
- [ ] Verify Library Independence: Ensure `StageRegistry` allows execution without Prefect/Ray dependencies.

### Phase 2: Prefect Orchestration (P1)
- [x] Refactor `DAGRunner` to support Prefect-driven execution via `TV_ORCH_MODE=prefect`.
- [x] Update `orchestration/flows/selection.py` to cover the full v4 HTR loop.
- [x] Implement `Zombie Purge` cleanup hooks for Ray workers.

### Phase 3: Lifecycle & Registry (P2)
- [ ] Automated Model Registration (Local): Implement logic to "tag" successful runs in `audit.jsonl` as candidates.
- [ ] Implement `context.diff()` for stage-level state auditing.
- [ ] Integrate MLflow metrics logging into `Inference` and `Synthesis` stages (using `MLflowTracker`).
- [ ] Fix `BacktestEngine` to use Pydantic `RunData` (dot notation) instead of dict access.

### Research Insights

**Industry Standards:**
- **A/B Deployment**: Use the MLflow Model Registry to tag "Champion" vs "Challenger" selection weights.
- **Forensic Ledger**: Maintain `audit.jsonl` alongside MLflow logs for redundancy and high-fidelity local research.
