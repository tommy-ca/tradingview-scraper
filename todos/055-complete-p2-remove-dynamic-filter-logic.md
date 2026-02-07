---
status: complete
priority: p2
issue_id: "055"
tags: [architecture, refactor, logic-leakage]
dependencies: []
created_at: 2026-02-05
completed_at: 2026-02-05
---

## Problem Statement
The `_apply_dynamic_filter` method in `BacktestEngine` performs asset filtering based on the `recommend_all` feature before the actual Selection stage, violating the Single Responsibility Principle and leaking domain logic into the orchestrator.

## Findings
- **Location**: `tradingview_scraper/backtest/engine.py`: Lines 488-520
- **Issue**: Domain logic (recommend_all filtering) is hardcoded in the orchestration layer instead of being part of the configurable Selection Engine.

## Resolution
Removed `_apply_dynamic_filter` from `BacktestEngine`.
The logic was redundant because `SelectionEngineV3` (and `v3.4`) implements a comprehensive filtering system including:
- Darwinian Health Gates (Regime Survival)
- Predictability Vetoes (Entropy, Hurst, Efficiency)
- Toxic Persistence checks
- High Friction (ECI) checks

The legacy `recommend_all` pre-filter is superseded by these robust selection mechanisms.

## Acceptance Criteria
- [x] `_apply_dynamic_filter` removed from `BacktestEngine`.
- [x] Logic verified as redundant in modern `SelectionEngine`.
- [x] Validated syntax.

## Work Log
- 2026-02-05: Identified during architecture review.
- 2026-02-05: Removed deprecated `_apply_dynamic_filter`. Validated that `SelectionEngine` (v3.4) handles rigorous candidate filtering via vetoes and scoring.
