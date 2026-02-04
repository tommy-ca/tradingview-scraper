---
title: "refactor: Modernize DataOps/MLOps Infrastructure (v2)"
type: refactor
date: 2026-02-03
status: revised_by_architectural_review
---

# refactor: Modernize DataOps/MLOps Infrastructure (v2)

## Overview

This plan outlines the modernization of the platform's DataOps and MLOps infrastructure. It focuses on replacing legacy script-based workflows with a robust `QuantSDK`-driven architecture, integrating **MLflow** for observability and **DVC** for data versioning.

*Revision Note: Phase 4 (Distributed Hydration) was removed based on architectural review to favor vertical scaling and simplicity. `StageContext` scope is restricted to top-level orchestration only.*

## Problem Statement / Motivation

1.  **Technical Debt**: Legacy scripts (e.g., `backfill_features.py`) are monolithic, handle their own I/O, and are difficult to test.
2.  **Lack of Observability**: Pipeline runs generate flat logs but no queryable metrics. Comparing "Production" vs "Canary" performance requires manual forensic analysis.
3.  **Reproducibility Gaps**: The Lakehouse is mutable. Re-running a backtest from last month against today's data yields different results.
4.  **Legacy Bloat**: Multiple competing ways to snapshot data (`WorkspaceManager`) and log telemetry (`ForensicSpanExporter`) create confusion.

## Proposed Solution

1.  **Observability (MLflow)**:
    -   Enhance `QuantSDK` to log metrics to MLflow for *observability only* (no control flow magic).
    -   **Simplification**: Delete legacy `ForensicSpanExporter` and consolidated telemetry.

2.  **Data Versioning (DVC)**:
    -   Use DVC for dataset versioning.
    -   **Simplification**: The Orchestrator (Makefile/CI) handles `dvc pull` commands. The `DataLoader` simply reads the files present on disk (standard filesystem access). It does *not* execute git/dvc commands dynamically.
    -   **Cleanup**: Delete `WorkspaceManager` and "Golden Snapshot" logic in favor of DVC commits.

3.  **Interface-First Refactor**:
    -   Refactor monolithic scripts into Services with **explicit signatures** (e.g., `service(date, symbol_list)`).
    -   Use a thin `StageContext` *only* at the top-level CLI/Controller layer to parse args, but do not pass it deep into business logic ("Context Trap").

## Technical Considerations

-   **Architecture**:
    -   **Explicit Dependencies**: Services must declare their needs (loaders, repos) explicitly, not via a global context.
    -   **Vertical Scaling**: Rely on vertical scaling or shared filesystems (NFS) for multi-process data access, avoiding complex "hydration" logic.
-   **Performance**:
    -   MLflow logging must be asynchronous.
-   **Security**:
    -   MLflow credentials handled via existing `Settings`.

## Acceptance Criteria

- [ ] **QuantSDK**: Pipeline stages log metrics to MLflow without affecting execution flow.
- [ ] **DVC**: Data is versioned via DVC; `DataLoader` reads from the current filesystem state without DVC coupling.
- [ ] **Migration**: `backfill_features.py` is refactored into a clean Service with explicit arguments.
- [ ] **Cleanup**: Legacy `WorkspaceManager` and `ForensicSpanExporter` are deleted.

## Success Metrics

-   **Observability**: 100% of pipeline metrics (row counts, nan% density) visible in MLflow UI.
-   **Code Quality**: Service signatures are explicit and testable without mocks.
-   **Cleanup**: Reduction of `scripts/` folder size and deletion of redundant snapshot/logging code.

## Dependencies & Risks

-   **Dependency**: Requires a running MLflow Tracking Server and S3/MinIO for DVC remote.
-   **Risk**: DVC usage requires team discipline (committing `.dvc` files).

## Implementation Phases

### Phase 1: MLOps Foundation (MLflow & Cleanup)
- [ ] Implement `MLflowAuditDriver` in `tradingview_scraper/utils/telemetry.py` (Observability only).
- [ ] **Refactor**: Delete legacy `tradingview_scraper/telemetry/exporter.py` (`ForensicSpanExporter`).
- [ ] Add `@mlflow_metric` helpers to `QuantSDK` (avoiding control-flow decorators).

### Phase 2: Data Versioning (DVC Setup)
- [ ] Initialize DVC in the repo.
- [ ] **Refactor**: Delete `tradingview_scraper/utils/workspace.py` (Golden Snapshots).
- [ ] Verify `DataLoader` works seamlessly with DVC-managed paths (standard filesystem access).

### Phase 3: Script Migration & Refactoring
- [ ] Define thin `StageContext` protocol in `tradingview_scraper/orchestration/models.py` (for CLI arg parsing only).
- [ ] Refactor `scripts/services/backfill_features.py` to use explicit arguments (decouple from Context).
- [ ] Refactor `scripts/services/ingest_data.py` to use explicit arguments.
- [ ] Update `scripts/run_production_pipeline.py` to orchestrate `dvc pull` before execution.

### Phase 4: [DELETED]
*Distributed Scaling (Ray) / ArtifactHydrator removed to avoid premature optimization and favor vertical scaling.*
