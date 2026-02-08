---
status: complete
priority: p1
issue_id: "097"
tags: [architecture, consistency, allocation]
dependencies: []
---

## Problem Statement
The `AllocationPipeline` (Pillar 3) stages currently do not follow the modular pattern established by the `SelectionPipeline`. `OptimizationStage` and `SimulationStage` are plain classes that lack the benefits of the `BasePipelineStage` abstraction.

## Findings
- **Location**: `tradingview_scraper/pipelines/allocation/stages/`
- **Issue**: Lack of standardized interface. Selection stages benefit from automatic `@validate_io` wrapping and `StageRegistry` integration, while Allocation stages do not.
- **Architectural Asymmetry**: Inconsistent developer experience across the triple-pipeline vision.

## Proposed Solutions

### Solution A: Standardize on BasePipelineStage (Recommended)
Refactor `OptimizationStage` and `SimulationStage` to inherit from `BasePipelineStage` (or a pillar-specific subclass).

**Pros:**
- Consistent interface across all pillars.
- Inherit automatic validation and logging logic.
- Enables registry-based stage discovery.

**Cons:**
- Requires minor refactoring of current implementation.

## Recommended Action
Implement Solution A. Create a shared base or use the existing `BasePipelineStage` for all Pillar 3 stages.

## Acceptance Criteria
- [x] `OptimizationStage` inherits from `BasePipelineStage`.
- [x] `SimulationStage` inherits from `BasePipelineStage`.
- [x] Stages are registered in `StageRegistry`.

## Work Log
- 2026-02-07: Identified during architectural review by Antigravity.
- 2026-02-08: Refactored `OptimizationStage` and `SimulationStage` to inherit from `BasePipelineStage`. Fixed circular imports and bug in `OptimizationStage`. Registered stages in `StageRegistry`. (Antigravity)
