---
title: "refactor: Modernize DataOps/MLOps Infrastructure (v2)"
type: refactor
date: 2026-02-03
status: completed
pull_request: "https://github.com/tommy-ca/tradingview-scraper/pull/7"
---

# refactor: Modernize DataOps/MLOps Infrastructure (v2)

## Enhancement Summary

**Deepened on:** 2026-02-03
**Sections enhanced:** 4
**Research agents used:** Architecture Strategist, Security Sentinel, Kieran Python Reviewer, Quant Backtest, Learnings Researcher

### Key Improvements
1.  **Strict Service Decoupling**: Validated the architectural separation of DVC (Infrastructure) from DataLoader (Application). Verified that backtesting works directly with filesystem paths.
2.  **Security Hardening**: Confirmed `SecurityUtils` usage in refactored services to prevent path traversal, matching institutional learnings.
3.  **Observability Pattern**: Validated the "Sidecar" pattern for MLflow, ensuring telemetry failures cannot crash production pipelines.

### New Considerations Discovered
-   **Environment Sync**: Backtesting now requires an explicit `make env-sync` to restore dependencies (`numba`, `nautilus-trader`) that were decoupled.
-   **Parameter Bloat Risk**: Warning identified against replacing "Context Trap" with excessive argument lists; recommended "Stateful Orchestrator" pattern for complex internal state.
-   **DVC Remote Security**: Explicit warning to NEVER commit S3 credentials to `.dvc/config`; usage of environment variables verified as the correct approach.

---

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

### Research Insights

**Best Practices:**
-   **Separation of Concerns**: Treat DVC as infrastructure. The application should assume data exists (Sidecar Pattern).
-   **Thin Context**: Use `StageContext` strictly for CLI parsing. Pass primitive types or domain objects to Services.
-   **Stateful Orchestrator**: For services with complex internal state, initialize configuration in `__init__` rather than passing 20+ arguments to every method.

**Security Considerations:**
-   **Path Traversal**: Continue using `SecurityUtils.get_safe_path()` in all new Service implementations.
-   **Credential Isolation**: Ensure AWS/S3 credentials for DVC are provided via environment variables (`AWS_ACCESS_KEY_ID`), never in `.dvc/config`.

**Edge Cases:**
-   **Missing Data**: If `dvc pull` fails silently, `DataLoader` must handle `FileNotFoundError` gracefully or fail fast with a clear "Run dvc pull" message.
-   **Environment Drift**: Major refactors can desync dependencies. Add `make env-sync` to CI pipelines.

## Technical Considerations

-   **Architecture**:
    -   **Explicit Dependencies**: Services must declare their needs (loaders, repos) explicitly, not via a global context.
    -   **Vertical Scaling**: Rely on vertical scaling or shared filesystems (NFS) for multi-process data access, avoiding complex "hydration" logic.
-   **Performance**:
    -   MLflow logging must be asynchronous.
-   **Security**:
    -   MLflow credentials handled via existing `Settings`.

## Acceptance Criteria

- [x] **QuantSDK**: Pipeline stages log metrics to MLflow without affecting execution flow.
- [x] **DVC**: Data is versioned via DVC; `DataLoader` reads from the current filesystem state without DVC coupling.
- [x] **Migration**: `backfill_features.py` is refactored into a clean Service with explicit arguments.
- [x] **Cleanup**: Legacy `WorkspaceManager` and `ForensicSpanExporter` are deleted.

## Success Metrics

-   **Observability**: 100% of pipeline metrics (row counts, nan% density) visible in MLflow UI.
-   **Code Quality**: Service signatures are explicit and testable without mocks.
-   **Cleanup**: Reduction of `scripts/` folder size and deletion of redundant snapshot/logging code.

## Dependencies & Risks

-   **Dependency**: Requires a running MLflow Tracking Server and S3/MinIO for DVC remote.
-   **Risk**: DVC usage requires team discipline (committing `.dvc` files).

## Implementation Phases

### Phase 1: MLOps Foundation (MLflow & Cleanup)
- [x] Implement `MLflowAuditDriver` in `tradingview_scraper/utils/telemetry.py` (Observability only).
- [x] **Refactor**: Delete legacy `tradingview_scraper/telemetry/exporter.py` (`ForensicSpanExporter`).
- [x] Add `@mlflow_metric` helpers to `QuantSDK` (avoiding control-flow decorators).

### Phase 2: Data Versioning (DVC Setup)
- [x] Initialize DVC in the repo.
- [x] **Refactor**: Delete `tradingview_scraper/utils/workspace.py` (Golden Snapshots).
- [x] Verify `DataLoader` works seamlessly with DVC-managed paths (standard filesystem access).

### Phase 3: Script Migration & Refactoring
- [x] Define thin `StageContext` protocol in `tradingview_scraper/orchestration/models.py` (for CLI arg parsing only).
- [x] Refactor `scripts/services/backfill_features.py` to use explicit arguments (decouple from Context).
- [x] Refactor `scripts/services/ingest_data.py` to use explicit arguments.
- [x] Update `scripts/run_production_pipeline.py` to orchestrate `dvc pull` before execution.

### Phase 4: [DELETED]
*Distributed Scaling (Ray) / ArtifactHydrator removed to avoid premature optimization and favor vertical scaling.*
