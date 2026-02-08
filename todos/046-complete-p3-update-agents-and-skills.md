---
status: complete
priority: p3
issue_id: "046"
tags: [documentation, agents, skills]
dependencies: []
---

# Update AGENTS.md and skills

Reflect that `BacktestEngine` is now the primary entry point for simulations across documentation and skill definitions.

## Problem Statement

Recent architectural shifts have promoted `BacktestEngine` to the central driver for all tournament-style simulations. Documentation and skills needed to be updated to reflect this "Backtest-First" workflow.

## Recommended Action
Update `AGENTS.md` and skill manifests to highlight `BacktestEngine` role.

## Acceptance Criteria

- [x] `AGENTS.md` contains an updated "Execution" section highlighting `BacktestEngine`.
- [x] Skill descriptions in `AGENTS.md` are technically accurate.
- [x] Documentation reflects the shift from "Scraper" to "Quant Platform".

## Work Log

### 2026-02-02 - Initial Discovery
**By:** Antigravity

### 2026-02-07 - Documentation Updated
**By:** Antigravity
- Updated `AGENTS.md` with "Stateful Orchestrator" details and clarified that `/quant-backtest` and `/quant-optimize` are powered by `BacktestEngine`.
