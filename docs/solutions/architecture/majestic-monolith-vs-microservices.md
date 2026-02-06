---
title: "Architecture Learning: Majestic Monolith vs. MLOps Microservices"
category: architecture
tags: [mlops, architecture, yagni, complexity]
module: Pipeline Orchestration
symptom: "Proposed architecture required running 3 external servers (Prefect, MLflow, Ray) just to run a local backtest."
root_cause: "Over-engineering ('Resume Driven Development') vs. solving the actual problem (Observability/Data Integrity)."
---

# Learning: The "Simplified Majestic Monolith" for Quant Pipelines

## Context
In Q1 2026, we planned to modularize the data pipelines. The initial proposal ("The Majestic Orchestrator") involved a full stack of:
- **Prefect**: For DAG orchestration and retries.
- **MLflow Server**: For model registry and experiment tracking.
- **Ray Cluster**: For distributed compute.
- **Pandera**: For data validation.

## The Problem
During review, it became clear that this stack violated **YAGNI (You Ain't Gonna Need It)** for a research-heavy quant platform:
1.  **Serialization Tax**: Passing state between Prefect tasks and Ray workers incurred massive serialization overhead ($O(N)$ data copies).
2.  **Infrastructure Weight**: Developers needed to spin up a Docker compose stack just to debug a strategy.
3.  **Complexity**: "Nested Runs" in MLflow created a database explosion without adding analytical value.

## The Solution: "Simplified Majestic Monolith"
We pivoted to a design that prioritizes **Library Stability** over **Orchestration Complexity**.

### Key Decisions
1.  **Engine-Agnostic Library**: The core logic (Stages, Engines) is written as a pure Python library. It *can* be orchestrated by Prefect, but it *must* run via a simple `runner.py` script.
2.  **Ledger as Truth**: Instead of a remote MLflow DB, the local `audit.jsonl` file is the immutable forensic record. MLflow is demoted to a "Visualization View" (write-only).
3.  **Reference-First State**: To solve the serialization tax, we pass `Ray.ObjectRef` or file paths in the context, never raw DataFrames.
4.  **2-Tier Validation**: We rejected "Validation on Every Step" (300% slowdown) in favor of **Tier 1 (Schema)** at Ingestion and **Tier 2 (Audit)** at final Allocation.

## Outcome
- **Performance**: Zero serialization overhead in the critical path.
- **Simplicity**: No external databases required for local dev.
- **Safety**: `ThreadSafeConfig` and Pandera provide the necessary guardrails without the operational weight.

## Lesson
**Don't build a rocket ship to go to the grocery store.** Start with a hardened library (Monolith) and layer orchestration only when the scale demands it.
