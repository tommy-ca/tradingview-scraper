---
status: pending
priority: p3
issue_id: "035"
tags: ['dx', 'tooling', 'data-ops']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
The current high-level AI skills (`/quant-select`, `/quant-backtest`, etc.) focus on the research and strategy lifecycle. However, common DataOps tasks such as ingesting new symbols or repairing gaps in historical data lack dedicated primitives, forcing agents to use generic `make` commands or manual script execution which is less deterministic and harder to trace.

## Findings
- **File**: `AGENTS.md` (Section 11: Claude Skills)
- **Current Skills**: `discover`, `select`, `backtest`, `optimize`.
- **Gap**: No dedicated skills for `data-fetch` (ingest) or `data-repair`.
- **Impact**: Agents often have to guess the correct `make` targets or environment variables for data ingestion and repair, leading to potential inconsistencies.

## Proposed Solutions

### Solution A: Add `quant-ingest` and `quant-repair` Skills
Implement two new skills using the `QuantSDK` that wrap the existing `make data-fetch` and `make data-repair` targets with standardized logging and error handling.

## Recommended Action
Define the `quant-ingest` and `quant-repair` skills in the project's skill registry. Update `AGENTS.md` to document these new capabilities.

## Acceptance Criteria
- [ ] `quant-ingest` skill implemented and tested.
- [ ] `quant-repair` skill implemented and tested.
- [ ] Skills documented in `AGENTS.md`.
- [ ] Skills integrated with the platform's telemetry and audit ledger.

## Work Log
- 2026-02-02: Issue identified during P3 findings review. Created todo file.
