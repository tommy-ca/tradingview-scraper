---
title: "chore: Rerun Pipelines for DataOps Validation"
type: chore
date: 2026-02-06
---

# chore: Rerun Pipelines for DataOps Validation

## Overview

This plan outlines the steps to verify the stability, correctness, and observability of the platform following the "DataOps Modularization" refactor. We will execute the data ingestion and alpha selection pipelines in `canary` mode, verifying that the new `Pandera` contracts, `ThreadSafeConfig`, and `MLflowTracker` are functioning as designed.

## Problem Statement / Motivation

Major architectural changes (Pydantic migration, ThreadSafeConfig, Pandera Validation) introduce regression risks. We need to confirm:
1.  **Safety**: The pipeline effectively filters toxic data without crashing ("Filter-and-Log").
2.  **Correctness**: `ThreadSafeConfig` prevents settings leakage in distributed runs.
3.  **Observability**: Metrics appear in MLflow (view-only) and the local Audit Ledger (source of truth).

## Proposed Solution

We will execute a 3-part validation sequence:
1.  **Golden Path**: Run a standard `make flow-production` to confirm end-to-end integrity.
2.  **Resilience Test**: Inject "toxic" data (mocked) to verify the "Filter-and-Log" mechanism.
3.  **Config Isolation Test**: Run a concurrent test to verify `ThreadSafeConfig` stability.

## Technical Approach

### Implementation Phases

#### Phase 1: Integration Testing (The Golden Path)
- Execute `make flow-production PROFILE=canary` (using Feature Flags).
- Verify `audit.jsonl` contains the new "Data Contract" entries.
- Verify `MLflow` received metrics (if server available).

#### Phase 2: Resilience Verification (Toxic Injection)
- Create `tests/ops/test_dataops_resilience.py`.
- Mock `DataLoader` to return a DataFrame with:
    - 1x Asset with `returns > 500%` (Toxic).
    - 1x Asset with valid data.
- Run `IngestionStage` and `BacktestEngine`.
- **Success Criteria**: Pipeline runs to completion; Toxic asset dropped; Valid asset processed; Audit log contains "Dropping invalid data".

#### Phase 3: Concurrency Verification (Config Isolation)
- Create `tests/ops/test_config_isolation.py`.
- Spawn 2x Threads with differing `ContextLocal` settings.
- Verify no leakage.

## Acceptance Criteria

### Functional Requirements
- [ ] `make flow-production` completes with exit code 0.
- [ ] `audit.jsonl` reflects "Data Contract" validation steps.
- [ ] "Toxic" data injection triggers a warning log, not a crash.

### Quality Gates
- [ ] New tests `tests/ops/test_dataops_resilience.py` pass.
- [ ] New tests `tests/ops/test_config_isolation.py` pass.

## Resource Requirements
- Local Python environment.
- No external MLflow/Prefect server required (due to "Simplified Majestic Monolith" design).

## References & Research
- `docs/design/selection_pipeline_v4_mlops.md`
- `docs/solutions/architecture/majestic-monolith-vs-microservices.md`
