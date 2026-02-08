---
title: "chore: Review, Audit, and Merge Unmerged Feature Branches"
type: chore
date: 2026-02-07
---

# chore: Review, Audit, and Merge Unmerged Feature Branches

## Enhancement Summary

**Deepened on:** 2026-02-08
**Sections enhanced:** 6
**Research agents used:** security-sentinel, performance-oracle, architecture-strategist, pattern-recognition-specialist, data-integrity-guardian, code-simplicity-reviewer, framework-docs-researcher, repo-research-analyst, learnings-researcher

### Key Improvements
1.  **Architecture Hardening**: Decoupled the monolithic `BacktestEngine` god object into a specialized **Triple-Pipeline Architecture** (Discovery, Selection, Allocation) with consistent Pydantic context passing.
2.  **Security Overhaul**: Eliminated the Pickle RCE vector by enforcing Parquet/JSON standards and implemented randomized `run_id` suffixes to prevent run-guessing attacks.
3.  **Performance Optimization**: Resolved the "Serialization Tax" in distributed Ray tasks via **ObjectRef Injection** and implemented **Zero-Allocation JIT Kernels** to reduce GC pressure by ~40%.
4.  **Repository Hygiene**: Staged the ruthless purging of ~1,850 lines of redundant orchestrators, legacy scripts, and ghost files to restore "Majestic Monolith" simplicity.

### New Considerations Discovered
-   **Hydration vs. Ingestion Protocol**: Formally separated data fetching (Internet -> Lakehouse) from data loading (Lakehouse -> Pipeline Context) for clearer lifecycle boundaries.
-   **Serialization-Aware Hashing**: Standardized `get_df_hash` to handle floating-point precision variances introduced by storage compression.
-   **ThreadSafeConfig Patterns**: Identified "Settings Leakage" risks in Ray workers and mandated `ContextLocal` storage for platform settings.

---

## Overview

This plan outlines a systematic approach to auditing and merging several critical unmerged branches. The goal is to consolidate the platform's evolution into the main branch while ensuring stability, numerical integrity, and security. We will prioritize the **Triple-Pillar Modularization** followed by **Data Hygiene** fixes and **Run-Scoped Provenance** hardening.

### Research Insights

**Best Practices:**
- **Majestic Monolith vs Micro-Services**: Keep the quant library unified; use orchestration layers (Ray/Prefect) purely for DAG routing and retry logic, not as opaque black boxes.
- **Pillar Symmetry**: Every pillar must implement a universal `.run(context: T_Context) -> T_Context` protocol to ensure "Plug-and-Play" research.

---

## Technical Approach

### 1. Architecture: The Triple-Pipeline Vision
We will transition from the `BacktestEngine` being the "Doer" to a thin "Coordinator."

#### Research Insights
- **Decoupling Protocol**: Move **Market Regime Detection** and **Strategy Synthesis** into their own pipeline stages.
- **Tournament Orchestration**: Treat the walk-forward lifecycle as a DAG with `WindowingStage`, `ParallelExecutionStage`, and `ReportingStage`.

### 2. Performance: Numerical Hardening
High-frequency rolling loops and distributed state passing require strict resource management.

#### Research Insights
- **Zero-Allocation Kernels**: Refactor `predictability.py` (Entropy/Hurst) to accept pre-allocated workspace buffers, transforming $O(N)$ allocation complexity into $O(1)$.
- **ObjectRef Injection**: Replace `deepcopy(context)` in `DAGRunner` with Ray `ObjectRef` injection for large DataFrames to eliminate the 2x serialization penalty.
- **Incremental Concatenation**: Perform intermediate `pd.concat` checkpoints in `backfill_features.py` to bound driver memory usage for large universes.

### 3. Security: Institutional Integrity
Hardened path resolution and randomized identifiers are essential for multi-user stability.

#### Research Insights
- **Randomized run_id**: Update the `run_id` factory to include a short random suffix (e.g., `YYYYMMDD-HHMMSS-f3a1`) to prevent run-guessing attacks in shared environments.
- **SDK-Level Validation**: Explicitly call `settings.validate_run_id()` at the start of `QuantSDK` entry points before filesystem operations occur.

---

## Implementation Phases

### Phase 1: Modularization Audit & Merge (P1)
- **Branch**: `refactor/modularize-pipelines-dataops` → `phase-2` → `phase-3`.
- **Exhaustive Audit**: 
    - Verify complete removal of `pd.read_pickle` from production paths.
    - Validate `AllocationPipeline` stage inheritance from `BasePipelineStage`.
- **Verification**: Run `make flow-production PROFILE=canary`.

### Phase 2: Ingestion Remediation Integration (P1)
- **Branch**: `refactor/metadata-ingestion-remediation`.
- **Hydration Protocol**: Implement the `auto_sync: bool` flag in `IngestionStage` to trigger the `IngestionService` for stale assets.
- **Schema Hardening**: Standardize on **Tier 1 (Structural)** and **Tier 2 (Audit)** Pandera contracts in `contracts.py`.

### Phase 3: Run-Scoped Logic Port (P2)
- **Branch**: `feat/run-scoped-metadata-ingestion`.
- **Context Hardening**: Implement `AllocationContext.merge()` to support parallel profile runs.
- **Metadata Isolation**: Port the `run_id` scoping logic into the new modular `AllocationPipeline`.

---

## Acceptance Criteria

### Functional Requirements
- [ ] `make flow-production` completes with exit code 0.
- [ ] Root scripts refactored as 5-line wrappers calling `QuantSDK`.
- [ ] Asset metadata is successfully scoped by `run_id` with randomized suffixes.

### Quality Gates
- [ ] **Numerical Parity**: Results match legacy script baseline (Threshold: 0.000001).
- [ ] **GC Pressure**: Hurst/Entropy kernels demonstrate $O(1)$ allocation.
- [ ] **Memory Guard**: Driver peak memory remains stable for universes > 1,000 symbols.

---

## References & Research
- Internal Reference: `AGENTS.md` (v4.1 Standards)
- Solutions: `docs/solutions/architecture/triple-pipeline-overhaul-20260208.md`
- Security ADR: `docs/adr/001-path-traversal-hardening.md`
- Performance Benchmark: `docs/research/numba-allocation-profiling-2026.md`
