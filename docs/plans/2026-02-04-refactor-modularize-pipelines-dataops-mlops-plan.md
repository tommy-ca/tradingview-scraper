---
title: "refactor: Modularize Data and Alpha Pipelines with Modern DataOps/MLOps Stack"
type: refactor
date: 2026-02-04
---

# refactor: Modularize Data and Alpha Pipelines with Modern DataOps/MLOps Stack

## Overview

This plan outlines the systematic modularization of the quantitative data and alpha (selection) pipelines using **Approach A: The Majestic Orchestrator**. We will integrate **Prefect** for orchestration, **MLflow** for experiment tracking, and **Pandera** for data contract enforcement. This transformation will move the platform from a custom sequential orchestrator to a production-grade MLOps ecosystem while adhering to SOLID, KISS, and YAGNI principles.

## Problem Statement / Motivation

1.  **Observability Gap**: The current `DAGRunner` provides limited visibility into stage-level failures and performance without manual log parsing.
2.  **Tracking Fragmentation**: Metrics (Sharpe, MaxDD) and artifacts (Selection JSONs) are scattered across the local run directories, making it difficult to compare historical "Champion" vs "Challenger" strategies.
3.  **Data Contract Fragility**: Schema drift and "toxic" data (e.g., volume spikes, price stalls) can propagate deep into the optimizer before detection, causing hard-to-debug solver failures.
4.  **Operational Friction**: Retrying failed stages or running pipelines in hybrid (Local/Cloud) environments requires manual intervention.

## Proposed Solution: Approach A (The Majestic Orchestrator)

We will layer a professional DataOps stack on top of the existing `BasePipelineStage` architecture.

1.  **Prefect (Orchestration)**: Elevate existing flows in `orchestration/flows/` to handle the DAG lifecycle. Wrap library stages in Prefect `@task` decorators with managed retries.
2.  **MLflow (Lifecycle)**: Implement a centralized `MLflowTracker` to log every run's parameters, metrics, and artifacts to a shared registry.
3.  **Pandera (Validation)**: Implement a `validate_io` decorator to enforce L0-L4 data contracts at every stage boundary (Ingestion, Features, Inference, Synthesis).

## Technical Considerations

-   **Reference-First State**: To avoid IPC overhead on Ray workers, `SelectionContext` will prioritize passing `Ray.ObjectRef` or file paths for large DataFrames instead of raw values.
-   **Run ID Syncing**: We will unify Prefect `flow_run_id`, MLflow `run_id`, and `SelectionContext.run_id` at the pipeline entry gate.
-   **Temporal-Aware Validation**: Pandera schemas will be modified to allow NaNs for assets prior to their genesis date to support multi-sleeve crypto runs.
-   **Zero-Allocation Synergy**: Integration with `NumericalWorkspace` will be maintained to ensure validation steps do not introduce unnecessary memory thrashing.

## Acceptance Criteria

- [ ] **Orchestration**: `make flow-production` successfully executes via a Prefect Flow.
- [ ] **Tracking**: 100% of pipeline runs appear in the MLflow UI with associated Sharpe, MaxDD, and artifact links.
- [ ] **Validation**: Pipeline fails fast with a clear `SchemaError` if "toxic" data (e.g., returns > 500%) is detected in the Ingestion stage.
- [ ] **Developer Experience**: A `TV_ORCH_MODE=local` flag allows running the DAG without external services for rapid debugging.
- [ ] **Performance**: Validation overhead remains < 5% of total pipeline execution time for standard 1000-asset universes.

## Implementation Phases

### Phase 1: Foundation & Validation (P1)
- [ ] Define global `ReturnsSchema` and `FeatureStoreSchema` in `tradingview_scraper/pipelines/contracts.py`.
- [ ] Implement `@validate_io` decorator in `selection/base.py`.
- [ ] Implement `MLflowTracker` utility in `tradingview_scraper/telemetry/`.

### Phase 2: Prefect Orchestration (P1)
- [ ] Refactor `DAGRunner` to support Prefect-driven execution.
- [ ] Update `orchestration/flows/selection.py` to cover the full v4 HTR loop.
- [ ] Implement `Zombie Purge` cleanup hooks for Ray workers.

### Phase 3: Lifecycle & Registry (P2)
- [ ] Implement automated "Model" registration for successful Selection policies.
- [ ] Add `context.diff()` method for stage-level state auditing.
- [ ] Integrate MLflow metrics logging into `Inference` and `Synthesis` stages.

## Success Metrics

- **Reliability**: 0 "Silent" data corruption errors reaching the optimizer.
- **Speed**: < 10 minutes for full crypto-sleeve production run (End-to-End).
- **Auditability**: 100% of production decisions traceable in MLflow.

## Dependencies & Risks

- **Dependency**: Requires local or remote MLflow and Prefect server instances.
- **Risk**: Serialization bottlenecks if DataFrames are passed by value (Mitigation: use `ObjectRef`).
- **Risk**: Schema Tax slowing down vectorized operations (Mitigation: use sampling or opt-in validation).

## References & Research

- **Internal Reference**: `AGENTS.md` (Pillar 1-3 standards).
- **MLOps Standard**: `selection_pipeline_v4_mlops.md`.
- **Learnings**: `docs/solutions/performance-issues/vectorized-optimization-bottlenecks.md`.

## MVP Code Example

### mlflow_tracker.py
```python
import mlflow

class MLflowTracker:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def log_metrics(self, metrics: dict):
        mlflow.log_metrics(metrics)

    def log_artifact(self, path: str):
        mlflow.log_artifact(path)
```

### base.py
```python
def validate_io(schema):
    def decorator(func):
        def wrapper(self, context, *args, **kwargs):
            # Validate Input
            # ...
            result = func(self, context, *args, **kwargs)
            # Validate Output
            schema.validate(result.returns_df)
            return result
        return wrapper
    return decorator
```
