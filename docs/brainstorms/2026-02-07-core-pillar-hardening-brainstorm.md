---
date: 2026-02-07
topic: core-pillar-hardening
---

# Brainstorm: Core Pillar Hardening (Approach A)

## What We're Building
A comprehensive refactor of the quantitative data and alpha pipelines into a **Triple-Pipeline Architecture**. This replaces the current monolithic `BacktestEngine` with three specialized, decoupled pipelines: **Discovery**, **Selection**, and **Allocation**. Each pipeline will be governed by strict Pydantic contexts and modular stages, ensuring compliance with SOLID, KISS, and modern DataOps/MLOps standards.

## Why This Approach
The current `BacktestEngine` is a "God Object" that has grown too complex to maintain or test reliably. By modularizing the allocation logic (Pillar 3) to match the existing modernization of selection (Pillar 1/2), we achieve:
1.  **Logical Purity**: Clear boundaries between "What to trade" (Selection) and "How much to trade" (Allocation).
2.  **Scalability**: Easier distribution of compute-intensive tasks across Ray clusters.
3.  **Numerical Stability**: Standardized data contracts at every handoff point prevent silent errors.
4.  **Operational Excellence**: Native telemetry and forensic ledger auditing in every stage.

## Key Decisions
- **Decision 1: Decompose `BacktestEngine`**: The engine is demoted from a "Doer" to a "Coordinator". It orchestrates the tournament loop but delegates all pillar logic to dedicated pipelines.
- **Decision 2: Formalize `AllocationPipeline`**: Create a new pipeline structure for Pillar 3 (Optimization, Simulation, Reporting) to mirror the successful `SelectionPipeline` (v4).
- **Decision 3: Pydantic-First Contexts**: Every pipeline will have a dedicated `Context` class (e.g., `AllocationContext`) inheriting from a shared base to ensure schema-enforced state passing.
- **Decision 4: Integrated Telemetry**: Promote MLflow and the Audit Ledger to first-class citizens accessible by any stage through a unified `TelemetryProvider`.

## Open Questions
- **Granularity of Simulation**: Should the `SimulationStage` remain as a wrapper for VBT/Nautilus, or should we expose more of the simulation state to the `AllocationContext`?
- **Meta-Pipeline Integration**: How will the recursive meta-portfolio logic fit into the new triple-pipeline structure?
- **Backward Compatibility**: To what extent do we need to maintain the legacy `BacktestOrchestrator` interfaces while transitioning to the V2 design?

## Next Steps
→ `/workflows:plan` to define the Phase 1 tasks:
1. Extract `AllocationPipeline` and initial stages.
2. Refactor `BacktestEngine` tournament loop.
3. Harden `SelectionPipeline` v4.1 with native telemetry.
