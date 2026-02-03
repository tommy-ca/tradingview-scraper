# DataOps v2 Migration Plan

## 1. Overview
This document outlines the migration of legacy data pipelines (Scanning, Ingestion, Meta-Enrichment) to the new **Lakehouse Architecture** using `flow-data`.

## 2. Legacy vs. Modern Workflow

| Feature | Legacy (`data-fetch`) | Modern (`flow-data`) |
| :--- | :--- | :--- |
| **Trigger** | Profile-based, inside `run_production_pipeline.py`. | Centralized `make flow-data` (Daily Cron). |
| **Ingestion** | `prepare_portfolio_data.py` (Ad-hoc API calls). | `ingest_data.py` (Idempotent Service). |
| **Metadata** | `meta-refresh` (Ad-hoc API calls). | `meta-ingest` (Centralized Catalog). |
| **Features** | None. | `feature-ingest` (TradingView Technicals). |
| **Storage** | Run-specific artifacts. | Centralized Lakehouse (Parquet) -> Run Snapshot. |

## 3. Migration Steps

### 3.1 Profile Updates
*   **Audit**: Verify all active profiles in `manifest.json`.
*   **Action**: Ensure `discovery` sections are correct, as `flow-data` uses them to generate candidates.

### 3.2 Scheduler Setup
*   **Cron**: Configure `0 0 * * * make flow-data` to keep the Lakehouse fresh.
*   **Gap Repair**: Configure `0 12 * * 0 make data-repair` (Weekly).

### 3.3 Orchestration Update
*   **Action**: `run_production_pipeline.py` is already updated to `lakehouse_only` mode.
*   **Validation**: Verify that running `flow-production` WITHOUT running `flow-data` first correctly fails/warns (or uses stale data if allowed).

## 4. Verification Plan (Phase 206)
1.  **Clean Slate**: Wipe `data/lakehouse`.
2.  **Full Cycle**: Run `make flow-data`.
    *   Verify `export/` has candidates.
    *   Verify `data/lakehouse/` has Parquet files.
    *   Verify `data/lakehouse/features/` has technicals.
3.  **Production Run**: Run `make flow-production`.
    *   Verify it runs without network I/O (check logs).

## 5. Agent-Native Integration (Architectural Enhancements)

To ensure this migration is discoverable and observable by the agent ecosystem:

### 5.1 Stage Registration
*   **Action**: Register the migration workflow as a formal pipeline stage in `StageRegistry`.
*   **ID**: `ops.migration.dataops_v2`
*   **Discovery**: Allows agents to find it via `scripts/quant_cli.py stage list --category ops`.
*   **Execution**: Enables execution via `QuantSDK.run_stage("ops.migration.dataops_v2")`.
*   **Verification**: Agents can dry-run the stage using `QuantSDK.validate_stage("ops.migration.dataops_v2")` to ensure prerequisites (credentials, disk space) are met before execution.

### 5.2 Transparency & Auditing
*   **Requirement**: `ingest_data.py` must emit structured audit events.
*   **Format**: JSONL entries in `data/artifacts/audit.jsonl`.
    ```json
    {
      "timestamp": "2026-02-03T10:00:00Z",
      "event": "ingest_progress",
      "run_id": "migration_v2_20260203",
      "symbol": "BTCUSDT",
      "rows": 1500,
      "status": "success",
      "progress": {
        "current": 45,
        "total": 150,
        "percent": 30.0,
        "eta_seconds": 120
      }
    }
    ```
*   **Agent Check**: Agents can tail this log to display real-time progress bars or make "patience vs. timeout" decisions.

### 5.3 Status Exposure
*   **State File**: The migration must maintain a machine-readable status file at `data/lakehouse/migration_status.json`.
*   **Schema**:
    ```json
    {
      "phase": "ingestion|verification|complete",
      "last_update": "2026-02-03T10:00:00Z",
      "health_check": "passed",
      "candidate_count": 150,
      "lock_id": "agent-session-xyz-123",
      "can_resume": true
    }
    ```
*   **Purpose**: Allows "Observer Agents" to gate downstream tasks (like `flow-production`) until `phase` is `complete`.
*   **Locking**: The `lock_id` prevents multiple agents from triggering the migration simultaneously.

### 5.4 Agent Control Primitives
To ensure true parity with human operators, the migration tool must expose granular controls:
*   **Pause/Resume**: Agents must be able to signal a pause (via `migration_control.json`) to free up bandwidth for higher-priority tasks, then resume later.
*   **Dry Run**: The script must support a `--dry-run` flag that simulates the migration (validating paths, permissions, and API limits) without moving data, returning a "success_probability" score.

