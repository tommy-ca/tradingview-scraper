---
title: "chore: Review, Audit, and Merge Unmerged Feature Branches"
type: chore
date: 2026-02-07
---

# chore: Review, Audit, and Merge Unmerged Feature Branches

## Overview

This plan outlines a systematic approach to auditing and merging several critical unmerged branches. The goal is to consolidate the platform's evolution into the main branch while ensuring stability, numerical integrity, and security. We will prioritize the **Triple-Pillar Modularization** (Discovery/Selection/Allocation) followed by **Data Hygiene** fixes and **Run-Scoped Provenance** hardening.

## Problem Statement / Motivation

The repository has diverged into several high-value feature branches that introduce conflicting refactors (e.g., moving `backtest_engine.py` to the library while other branches still target the root script).
- **Stagnation**: Valuable features (Vectorized Synthesis, Run-Scoped Metadata) are not yet available in `main`.
- **Merge Complexity**: The longer these branches remain unmerged, the harder the eventual integration becomes due to "God Object" refactors and directory restructures.
- **Risk**: Overlapping implementations of ingestion and backtesting logic increase the risk of "split-brain" bugs.

## Proposed Solution: The Sequential Integration Strategy

We will merge branches in a specific order to minimize conflict complexity and establish a stable foundation for the next layer of features.

### Priority 1: Modularize Pipelines (Phases 1-3)
These branches establish the new directory structure and decouple the core pillars.
1.  **Phase 1 (DataOps)**: Storage migration (Pickle → Parquet) and `DataLoader` standard.
2.  **Phase 2 (Orchestration)**: `OrchestrationRunner` and Ray cleanup hooks.
3.  **Phase 3 (Triple Pipeline)**: Extraction of `AllocationPipeline` and removal of `BacktestEngine` god-methods.

### Priority 2: Ingestion Remediation
Apply schema hardening (`pandera`) and performance fixes to the now-modularized ingestion stages.

### Priority 3: Run-Scoped Metadata
Port the complex "Run-Scoped" logic into the new modular `AllocationPipeline` and `IngestionService`.

## Technical Considerations

- **The `backtest_engine.py` Move**: Phase 3 moves the engine to `tradingview_scraper/backtest/engine.py`. A global grep/replace of root-level imports is required.
- **Competing Ingestion Logic**: We will adopt a **Hydration vs. Ingestion** protocol:
    - **Hydration**: Internet → Lakehouse (`IngestionService`).
    - **Ingestion**: Lakehouse → Pipeline Context (`IngestionStage`).
- **State Management**: Every merge must preserve the `NumericalWorkspace` lifecycle and zero-lookahead integrity.

## Acceptance Criteria

### Integration Milestone 1 (Modularization)
- [ ] Phase 1-3 branches merged into `main` sequentially.
- [ ] Root scripts (`natural_selection.py`, etc.) refactored as thin wrappers calling the library.
- [ ] `make flow-production` executes successfully using the new `AllocationPipeline`.

### Integration Milestone 2 (Data Hygiene & Scoping)
- [ ] `IngestionValidator` correctly drops "toxic" data (>500% moves) via Pandera contracts.
- [ ] Asset metadata is successfully scoped by `run_id` in the Lakehouse.

### Quality Gates
- [ ] **Numerical Parity**: Results from the modularized engine match the legacy script baseline (Threshold: 0.000001).
- [ ] **Zero Look-Ahead**: `DataLoader` verified to slice data correctly before training windows.
- [ ] **Security**: `ensure_safe_path` prevents traversal attacks in all updated entry points.

## Implementation Phases

### Phase 1: Modularization Audit & Merge
- **Branch**: `refactor/modularize-pipelines-dataops` → `phase-2` → `phase-3`.
- **Task**: Sequential exhaustive audit (Security, Architecture, Performance).
- **Verification**: Run `make flow-production PROFILE=canary`.

### Phase 2: Ingestion Remediation Integration
- **Branch**: `refactor/metadata-ingestion-remediation`.
- **Task**: Rebase/Port `pandera` schema fixes into the new `IngestionStage`.
- **Verification**: Inject synthetic toxic data and verify it is filtered without crashing.

### Phase 3: Run-Scoped Logic Port
- **Branch**: `feat/run-scoped-metadata-ingestion`.
- **Task**: Port the `run_id` metadata isolation into the `AllocationPipeline` context.
- **Verification**: Verify that two concurrent runs with different metadata remain isolated.

## Success Metrics
- **LOC Reduction**: ~2,000 lines of redundant/dead code removed.
- **Speed**: Vectorized synthesis provides 100x speedup for Pillar 2.
- **Reproducibility**: 100% of metadata is scoped to specific runs.

## Dependencies & Risks
- **Risk**: "Refactor Overlap". High risk of conflicts in `settings.py` and `backtest/engine.py`.
- **Mitigation**: Perform small, frequent commits during the manual merge process.
- **Dependency**: Requires `gh` CLI for PR management and `pytest` for parity verification.

## References & Research
- Internal: `AGENTS.md` (3-Pillar Standards)
- Solutions: `docs/solutions/architecture/triple-pipeline-overhaul-20260208.md`
- Specs: `docs/specs/requirements_v3.md`
