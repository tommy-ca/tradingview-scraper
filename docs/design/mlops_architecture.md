# Design: MLOps Hybrid Architecture

## 1. Overview
The architecture follows a **Hybrid Execution Model** where the workflow logic (Orchestration) is decoupled from the heavy numerical computation (Compute Engine).

## 2. Component Design

### 2.1 Orchestration (Prefect)
- **Flows**: Each sleeve execution (TradFi, Crypto) or Meta-Portfolio run is a Prefect Flow.
- **Tasks**: Granular steps (Discovery, Fetch, Audit) are wrapped as Prefect Tasks.
- **State Management**: Uses Prefect's API to track success/failure and persist audit logs centrally.

### 2.2 Distributed Compute (Ray)
- **Actor Model**: Use Ray Actors for long-lived state (e.g., maintaining historical price data in memory across backtest windows).
- **Parallel Optimization**: 
    - `optimize_clustered_v2.py` will launch Ray tasks for each risk profile in parallel.
- **Parallel Backtesting**:
    - `backtest_engine.py` will parallelize engine/simulator combinations within each sequential time window.

### 2.3 Data Storage (Lakehouse v2)
- Local `data/lakehouse` becomes a local cache.
- **Remote Store**: S3/MinIO bucket via `fsspec`.
- **Serialization**: Transition from `.pkl` to `.parquet` for returns matrices to improve distributed load performance and schema enforcement.

### 2.4 Performance Hardening: The "Slim" Pattern
To maximize Ray throughput, the architecture enforces **Lazy Analytics**:
- **Loop Metrics**: Uses vectorized `numpy` code for $O(1)$ latency during backtest iterations.
- **Lazy Imports**: Heavy libraries (`quantstats`) are only imported inside specific report-generation functions to avoid bloating Ray task overhead.
- **Pre-computed Hashes**: Hashes for data integrity (Audit Ledger) are computed once and passed as metadata rather than re-computed in remote tasks.

## 3. Infrastructure Isolation

### 3.1 Environment Variable Propagation
To ensure remote workers maintain parity with the head node:
- **`TV_` Prefix**: All environment variables prefixed with `TV_` must be automatically captured and passed to `ray.init(runtime_env={"env_vars": ...})`.
- **`PYTHONPATH`**: The project root must be explicitly added to worker paths to resolve the `tradingview_scraper` module.

### 3.2 SkyPilot Integration
SkyPilot will handle:
- **Cluster Lifecycle**: Provisioning on AWS/GCP Spot instances.
- **Ray Orchestration**: Setting up the head and worker nodes automatically.
- **Isolated Env**: Provisioning runs in a `Pydantic v1` compatible environment separate from the quantitative library.

## 4. Execution Flow
1. **User** triggers `make flow-production`.
2. **Make** calls `uv run flows/production_flow.py`.
3. **Prefect Flow** starts, initializes a **Ray Cluster** via SkyPilot if needed.
4. **Lightweight Tasks** run on the local machine.
5. **Heavy Tasks** are sent to Ray workers.
6. **Results** are collected, stored in S3, and summarized in a final report.
