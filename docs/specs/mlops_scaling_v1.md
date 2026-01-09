# MLOps Scaling Specification (v1)

## 1. Objective
Transition the current single-node, script-based pipeline to a scalable, distributed MLOps architecture. Enable multi-node processing for heavy workloads (Backtesting Tournaments, Parameter Sweeps, Global Optimization) while improving observability and maintainability.

## 2. Requirements

### 2.1 Scalability
- **Distributed Compute**: Support executing heavy tasks (e.g., 1000+ backtests, large matrix inversions) across a cluster.
- **Dynamic Provisioning**: Capability to spin up/down resources (High-CPU nodes) on-demand.
- **Parallel Optimization**: Parallelize multi-profile optimization (HRP, Max Sharpe, etc.) within a single run.

### 2.2 Orchestration
- **Workflow Management**: Replace `subprocess` calls with a DAG-based orchestrator (Prefect).
- **Observability**: Centralized dashboard for task status, logs, and artifacts.
- **Resilience**: Automated retries, caching of successful steps, and state persistence.

### 2.3 Data Infrastructure
- **Remote Storage**: Transition from local `data/lakehouse` to S3-compatible storage for cluster access.
- **Artifact Versioning**: Ensure manifests and returns matrices are versioned and traceable across distributed runs.

### 2.4 Monitoring & Benchmarking
- **Latency Heatmap**: The system must identify which parts of the pipeline take the most time (e.g., specific optimizers like HRP).
- **Cost Analysis**: Track simulated cloud costs for Ray cluster runs.
- **Baseline Metrics**: Establish sequential runtimes to quantify the speedup ratio of distributed execution.

## 3. Technology Stack

| Component | Selected Tool | Justification |
| :--- | :--- | :--- |
| **Compute Engine** | **Ray** | Distributed Python execution; minimal code changes (@ray.remote). |
| **Orchestrator** | **Prefect** | Lightweight, Python-native DAG management; excellent UI. |
| **Infra Manager** | **SkyPilot** | Target infrastructure provider (Requires Pydantic v1 isolation). |
| **Storage** | **S3 / MinIO** | Standard object storage for distributed state. |

## 4. Implementation Findings & Performance Requirements

### 4.1 Dependency Isolation
- **Issue**: Infrastructure tools like `SkyPilot` and `dstack` have version conflicts with `Pydantic v2`.
- **Requirement**: Infrastructure provisioning must be kept in a separate environment or executed via isolated CLI calls to avoid polluting the core quantitative library's dependency tree.

### 4.2 The "Slim Metrics" Pattern
- **Issue**: Heavy library imports (`quantstats`, `seaborn`) on remote Ray nodes create linear latency scaling during task startup.
- **Requirement**: Quantitative utilities MUST support "Slim Mode" (using only `numpy`/`pandas`) for high-frequency loops (e.g., backtest windows). Detailed analytical libraries MUST be lazy-loaded only when generating final reports.

### 4.3 Hybrid Execution Lifecycle
- **Local Control**: Orchestration (Prefect) and Lightweight Data Aggregation MUST run locally to minimize egress costs and latency.
- **Remote Compute**: Large-scale optimizations (800+ serial tasks) MUST be offloaded to Ray Cluster workers using `@ray.remote`.
