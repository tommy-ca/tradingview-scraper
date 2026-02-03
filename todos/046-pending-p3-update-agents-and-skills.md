---
status: pending
priority: p3
issue_id: "046"
tags: [documentation, agents, skills]
dependencies: []
---

# Update AGENTS.md and skills

Reflect that `BacktestEngine` is now the primary entry point for simulations across documentation and skill definitions.

## Problem Statement

Recent architectural shifts have promoted `BacktestEngine` to the central driver for all tournament-style simulations, replacing older entry points and the "Scraper" centric view. However, `AGENTS.md` and some Claude skill descriptions may still contain legacy references or lack clarity on the new "Backtest-First" workflow.

Ensuring agents have up-to-date documentation is critical for maintaining "Agent-Native" standards where agents can discover and utilize the primary tools correctly.

## Findings

- `AGENTS.md` mentions `make flow-production` but could more explicitly highlight the `BacktestEngine` role in the "3-Pillar Architecture".
- Claude skills like `/quant-backtest` rely on the `QuantSDK`, which in turn wraps `BacktestEngine`. This chain should be clearly documented for agents.
- There is no explicit mention of the "Stateful Orchestrator Pattern" recently introduced to `BacktestEngine` in `AGENTS.md`.

## Proposed Solutions

### Option 1: Update AGENTS.md and Skill Manifests (Recommended)

**Approach:**
1.  Revise `AGENTS.md` to include a section on `BacktestEngine` and its role in coordinating Pillar 2 (Alpha) and Pillar 3 (Allocation).
2.  Update the description of `/quant-backtest` and `/quant-optimize` in `AGENTS.md` (Section 11) to mention they are powered by the tournament engine.
3.  Add a "State management" section to `AGENTS.md` explaining how `BacktestEngine` handles recursive sleeve state.

**Pros:**
- Better guidance for autonomous agents.
- Alignment between documentation and implementation.

**Cons:**
- Documentation only; no functional changes.

**Effort:** 1-2 hours

**Risk:** None

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `AGENTS.md`
- `tradingview_scraper/sdk.py` (Docstrings)
- `tradingview_scraper/pipelines/backtest/base.py` (Docstrings)

## Acceptance Criteria

- [ ] `AGENTS.md` contains an updated "Execution" section highlighting `BacktestEngine`.
- [ ] Skill descriptions in `AGENTS.md` are technically accurate.
- [ ] Documentation reflects the shift from "Scraper" to "Quant Platform".

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Reviewed `AGENTS.md` content against recent `BacktestEngine` refactors.
- Identified documentation gaps regarding the "Stateful Orchestrator Pattern".
- Drafted update plan in todo 046.

## Notes

- Keep the tone of `AGENTS.md` professional and direct, as per the CLI guidelines.
- Ensure the "Key Developer Commands" table remains synchronized with the `Makefile`.
