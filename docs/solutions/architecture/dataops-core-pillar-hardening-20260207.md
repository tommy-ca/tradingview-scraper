---
category: architecture
tags: [dataops, security, performance, validation, pydantic, pandera]
module: data-ingestion
symptoms: [rce-risk, path-traversal, settings-leakage, data-corruption, serialization-overhead]
---

# DataOps Core Pillar Hardening

## Problem
As the quantitative platform scaled to support multi-asset meta-portfolios and parallel Ray execution, several "Core Pillar" vulnerabilities emerged:
1.  **Security (RCE & Traversal)**: Reliance on `pickle` for data persistence created a Remote Code Execution (RCE) vector. Insecure `run_id` and symbol handling allowed potential path traversal.
2.  **State Contamination**: The global singleton settings pattern caused "settings leakage" across parallel Ray tasks, where concurrent simulations would overwrite each other's parameters.
3.  **Data Integrity**: Lack of formal schema enforcement allowed "toxic" data (e.g., zero-filled weekends for TradFi, returns > 1000%) to corrupt optimizer calculations without clear audit trails.
4.  **Performance Bottlenecks**: Passing large raw DataFrames across Ray nodes caused massive serialization overhead.

## Solution: The "Simplified Majestic Monolith" Pivot
The platform was refactored to prioritize **Library Stability** and **Deterministic Execution** over orchestration complexity.

### 1. Thread-Safe & Context-Aware Configuration
Implemented `ThreadSafeConfig` using Python `ContextVars`. 
- **Isolation**: Each Ray task or thread maintains its own isolated `TradingViewScraperSettings` instance.
- **Priority**: `get_settings()` checks the `ContextVar` first, falling back to a global singleton only if no context is set.
- **Validation**: Migrated settings to **Pydantic (v2)** for strict runtime type enforcement and automatic manifest parsing.

### 2. Multi-Tier Data Contracts (Pandera)
Introduced a two-tier validation strategy in `tradingview_scraper/pipelines/contracts.py`:
- **Tier 1 (Structural)**: `ReturnsSchema` ensures basic shape, types, and required columns (`date`, `symbol`, `returns`).
- **Tier 2 (Semantic/Audit)**: `AuditSchema` enforces business logic invariants, such as:
    - **No Weekend Padding**: Rejects TradFi assets with zero-filled weekends.
    - **Toxicity Bounds**: Bounded returns within [-100%, +1000%] to prevent optimizer divergence.

### 3. "Filter-and-Log" Pipeline Strategy
Instead of crashing on invalid data, the pipeline now employs a "Lazy Validation" approach via the `@validate_io` decorator:
- **Resilience**: Stages validate their outputs. If certain assets fail the data contract, they are dropped from the context.
- **Observability**: Dropped assets are recorded in the `SelectionContext.audit_trail`, ensuring the reason for exclusion is forensic and traceable.

### 4. Security Hardening
- **Removal of Pickle RCE**: Standardized on **Parquet** for dataframes and **JSON** for metadata. Legacy pickle loading is gated behind `ensure_safe_path` and issues a deprecation warning.
- **Path Traversal Guard**: Implemented strict regex-based whitelist validation for `run_id` and `symbol` in both `TradingViewScraperSettings` and `SelectionContext`.
- **Security Anchoring**: `DataLoader.ensure_safe_path` explicitly anchors all filesystem operations to a whitelist of allowed institutional root directories.

### 5. Reference-First State Management
Optimized Ray performance by shifting from "Data-Passing" to "Reference-Passing":
- **Low Overhead**: Large objects are passed as `Ray.ObjectRef` or file paths.
- **Deterministic Paths**: The `DataLoader` manages deterministic path resolution across nodes, ensuring workers can load data directly from the Lakehouse.

## Prevention Strategy
- **Audit Everything**: Every drop or filter action must be backed by an entry in `audit.jsonl`.
- **YAGNI on Orchestration**: Keep core logic runnable as simple Python scripts. Don't hide complexity inside orchestration tool (Ray/Prefect) specific features.
- **Schema First**: Define Pandera schemas before implementing new alpha signals.

## Related Documentation
- [AGENTS.md](../../../AGENTS.md): Core platform principles and 3-Pillar architecture.
- [Majestic Monolith vs Microservices](./majestic-monolith-vs-microservices.md): Architectural philosophy.
- [Path Traversal Hardening](../security-issues/path-traversal-hardening-SecurityUtils-20260201.md): Deep dive into symbol sanitization.
- [Thread-Safe Config](../runtime-errors/thread-safe-config-BacktestEngine-20260202.md): Specific fix for BacktestEngine race conditions.
